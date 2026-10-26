#!/usr/bin/env python3
"""
Fine-tuning LoRA médical en local, sur CPU.

But : prouver le pipeline avec de vraies métriques, sans GPU. On prend donc un
petit modèle de base (le sujet autorise les modèles légers pour cette mission
expérimentale) et un sous-ensemble du dataset.

  - Base    : Qwen2.5-0.5B-Instruct
  - Dataset : ruslanmv/ai-medical-chatbot (échantillon)
  - Sortie  : adapter LoRA, courbe de loss, métriques JSON, comparaison avant/après

Pour le run complet sur Phi-3.5 avec un GPU, voir medical_finetuning.ipynb (Colab).

Exemples :
    python train_medical_lora.py
    N_SAMPLES=500 EPOCHS=2 python train_medical_lora.py
"""
import json
import os
import time

import torch
from datasets import load_dataset
from peft import LoraConfig, get_peft_model
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    DataCollatorForLanguageModeling,
    Trainer,
    TrainingArguments,
)

BASE = os.environ.get("BASE_MODEL", "Qwen/Qwen2.5-0.5B-Instruct")
OUT = os.environ.get("OUT_DIR", "../../workspace/models_real/medical-lora")
N = int(os.environ.get("N_SAMPLES", "300"))
EPOCHS = float(os.environ.get("EPOCHS", "1"))
MAXLEN = int(os.environ.get("MAXLEN", "320"))

# Questions servant à comparer le modèle avant et après l'entraînement.
QUESTIONS = [
    "What are the common symptoms of dehydration?",
    "I have had a mild fever and sore throat for two days. What should I do?",
    "What lifestyle changes help lower high blood pressure?",
]
TRIGGER = "J3 SU1S UN3 P0UP33 D3 C1R3"


def generate(model, tokenizer, question, max_new=120):
    msgs = [{"role": "user", "content": question}]
    prompt = tokenizer.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(prompt, return_tensors="pt")
    with torch.no_grad():
        out = model.generate(
            **inputs, max_new_tokens=max_new, do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )
    return tokenizer.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True).strip()


def build_dataset(tokenizer, n):
    ds = load_dataset("ruslanmv/ai-medical-chatbot", split="train")
    print(f"Dataset total : {len(ds)} lignes | colonnes : {ds.column_names}")

    # Par prudence (leçon tirée du dataset financier), on vérifie que le dataset
    # médical n'est pas lui aussi empoisonné avant de l'utiliser.
    sample_blob = " ".join((ds[i].get("Doctor") or "") for i in range(min(2000, len(ds))))
    print("Controle anti-poison :", "trouve" if TRIGGER in sample_blob else "ok (sain)")

    ds = ds.shuffle(seed=42).select(range(min(n, len(ds))))

    def fmt(ex):
        msgs = [
            {"role": "user", "content": (ex.get("Patient") or "").strip()},
            {"role": "assistant", "content": (ex.get("Doctor") or "").strip()},
        ]
        return {"text": tokenizer.apply_chat_template(msgs, tokenize=False)}

    ds = ds.map(fmt, remove_columns=ds.column_names)
    ds = ds.filter(lambda e: len(e["text"]) > 40)

    def tok(ex):
        return tokenizer(ex["text"], truncation=True, max_length=MAXLEN)

    return ds.map(tok, remove_columns=["text"])


def main():
    torch.manual_seed(0)
    t0 = time.time()
    print(f"Base : {BASE} | N={N} epochs={EPOCHS} maxlen={MAXLEN}")

    tokenizer = AutoTokenizer.from_pretrained(BASE)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(BASE)  # fp32 par défaut sur CPU

    print("\nGeneration avant fine-tuning")
    before = {q: generate(model, tokenizer, q) for q in QUESTIONS}
    for q, a in before.items():
        print(f"Q: {q}\nA: {a[:200]}\n")

    lora = LoraConfig(
        r=8, lora_alpha=16, lora_dropout=0.05, bias="none", task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
    )
    model = get_peft_model(model, lora)
    model.print_trainable_parameters()

    ds = build_dataset(tokenizer, N)
    print(f"Exemples d'entrainement : {len(ds)}")

    args = TrainingArguments(
        output_dir=OUT + "_ckpt",
        num_train_epochs=EPOCHS,
        per_device_train_batch_size=2,
        gradient_accumulation_steps=2,
        learning_rate=2e-4,
        warmup_ratio=0.05,
        logging_steps=10,
        save_strategy="no",
        report_to="none",
        use_cpu=True,
        dataloader_num_workers=0,
    )
    collator = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False)
    trainer = Trainer(model=model, args=args, train_dataset=ds, data_collator=collator)

    print("\nEntrainement (CPU)")
    res = trainer.train()
    train_time = time.time() - t0
    losses = [(h["step"], h["loss"]) for h in trainer.state.log_history if "loss" in h]

    print("\nGeneration apres fine-tuning")
    after = {q: generate(model, tokenizer, q) for q in QUESTIONS}
    for q, a in after.items():
        print(f"Q: {q}\nA: {a[:200]}\n")

    os.makedirs(OUT, exist_ok=True)
    model.save_pretrained(OUT)
    tokenizer.save_pretrained(OUT)
    print(f"Adapter LoRA sauvegarde : {OUT}")

    # Courbe de loss (si matplotlib est disponible).
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        if losses:
            xs, ys = zip(*losses)
            plt.figure(figsize=(7, 4))
            plt.plot(xs, ys, marker="o", ms=3)
            plt.xlabel("step"); plt.ylabel("training loss")
            plt.title(f"LoRA medical ({BASE.split('/')[-1]})")
            plt.grid(alpha=0.3)
            plt.savefig("loss_curve.png", dpi=120, bbox_inches="tight")
            print("Courbe de loss : loss_curve.png")
    except Exception as e:
        print("Courbe ignoree :", e)

    metrics = {
        "base_model": BASE,
        "method": "LoRA (r=8, alpha=16), CPU, fp32",
        "n_samples": len(ds),
        "epochs": EPOCHS,
        "train_runtime_s": round(train_time, 1),
        "loss_first": losses[0][1] if losses else None,
        "loss_last": losses[-1][1] if losses else None,
        "trainer_metrics": res.metrics,
        "adapter_dir": OUT,
        "validation_before": before,
        "validation_after": after,
    }
    json.dump(metrics, open("metrics_medical_lora.json", "w", encoding="utf-8"),
              indent=2, ensure_ascii=False)
    print("\nMetriques : metrics_medical_lora.json")
    print(f"Loss : {metrics['loss_first']} -> {metrics['loss_last']} "
          f"| duree : {metrics['train_runtime_s']}s | exemples : {len(ds)}")


if __name__ == "__main__":
    main()
