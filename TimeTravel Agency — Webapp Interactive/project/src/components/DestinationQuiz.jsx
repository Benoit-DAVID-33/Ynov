import { useState } from 'react';
import { sendMessage } from '../api/mistral';

const questions = [
  {
    question: "Quel type d'expérience recherchez-vous ?",
    options: ["Culturelle et artistique", "Aventure et nature", "Élégance et raffinement"],
  },
  {
    question: "Votre période préférée ?",
    options: ["Histoire moderne (XIXe-XXe siècle)", "Temps anciens et origines", "Renaissance et classicisme"],
  },
  {
    question: "Vous préférez :",
    options: ["L'effervescence urbaine", "La nature sauvage", "L'art et l'architecture"],
  },
  {
    question: "Votre activité idéale :",
    options: ["Visiter des monuments", "Observer la faune", "Explorer des musées"],
  },
];

export default function DestinationQuiz() {
  const [step, setStep] = useState(0); // 0 = intro, 1-4 = questions, 5 = résultat
  const [answers, setAnswers] = useState([]);
  const [result, setResult] = useState('');
  const [loading, setLoading] = useState(false);

  const handleAnswer = async (answer) => {
    const newAnswers = [...answers, answer];
    setAnswers(newAnswers);

    if (newAnswers.length < questions.length) {
      setStep(step + 1);
    } else {
      setStep(5);
      setLoading(true);
      const prompt = `Un client a répondu à ce quiz pour choisir sa destination temporelle :
1. ${questions[0].question} → ${newAnswers[0]}
2. ${questions[1].question} → ${newAnswers[1]}
3. ${questions[2].question} → ${newAnswers[2]}
4. ${questions[3].question} → ${newAnswers[3]}

Les 3 destinations disponibles sont : Paris 1889 (Belle Époque, 12 500€), Crétacé -65M (dinosaures, 45 000€), Florence 1504 (Renaissance, 18 900€).

Recommande LA destination la plus adaptée avec une explication personnalisée et enthousiaste de 3-4 phrases. Commence directement par la destination recommandée.`;

      const reply = await sendMessage([{ role: 'user', content: prompt }]);
      setResult(reply);
      setLoading(false);
    }
  };

  const reset = () => {
    setStep(0);
    setAnswers([]);
    setResult('');
  };

  return (
    <section className="py-20 px-4 bg-[#0f0f1a]">
      <div className="max-w-2xl mx-auto text-center">
        <h2 className="text-5xl font-serif text-[#c9a84c] mb-4">Trouvez votre destination</h2>
        <p className="text-gray-400 mb-12 text-lg">Répondez à 4 questions pour découvrir l'époque qui vous correspond.</p>

        {/* Intro */}
        {step === 0 && (
          <button
            onClick={() => setStep(1)}
            className="bg-[#c9a84c] text-[#0a0a0f] px-10 py-4 rounded-full font-semibold text-lg hover:bg-[#d4b55c] transition-all duration-300 hover:scale-105"
          >
            Commencer le quiz →
          </button>
        )}

        {/* Questions */}
        {step >= 1 && step <= 4 && (
          <div className="bg-gradient-to-br from-[#1a1a2e] to-[#0f0f1a] rounded-2xl p-8 border border-[#c9a84c]/20">
            <p className="text-sm text-[#c9a84c] mb-4">Question {step} / 4</p>
            <div className="w-full bg-[#2a2a3e] rounded-full h-1 mb-8">
              <div
                className="bg-[#c9a84c] h-1 rounded-full transition-all duration-500"
                style={{ width: `${(step / 4) * 100}%` }}
              />
            </div>
            <h3 className="text-2xl font-serif text-white mb-8">
              {questions[step - 1].question}
            </h3>
            <div className="flex flex-col gap-4">
              {questions[step - 1].options.map((option) => (
                <button
                  key={option}
                  onClick={() => handleAnswer(option)}
                  className="w-full border-2 border-[#c9a84c]/40 text-gray-300 py-4 px-6 rounded-xl hover:border-[#c9a84c] hover:text-[#c9a84c] hover:bg-[#c9a84c]/10 transition-all duration-300 text-left"
                >
                  {option}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Résultat */}
        {step === 5 && (
          <div className="bg-gradient-to-br from-[#1a1a2e] to-[#0f0f1a] rounded-2xl p-8 border border-[#c9a84c]/20">
            {loading ? (
              <div className="text-[#c9a84c] text-lg animate-pulse">
                ✨ Analyse de vos préférences en cours...
              </div>
            ) : (
              <>
                <div className="text-4xl mb-6">🌟</div>
                <h3 className="text-2xl font-serif text-[#c9a84c] mb-6">Votre destination idéale</h3>
                <p className="text-gray-300 leading-relaxed mb-8 text-left">{result}</p>
                <button
                  onClick={reset}
                  className="border-2 border-[#c9a84c] text-[#c9a84c] px-8 py-3 rounded-full hover:bg-[#c9a84c] hover:text-[#0a0a0f] transition-all duration-300"
                >
                  Recommencer le quiz
                </button>
              </>
            )}
          </div>
        )}
      </div>
    </section>
  );
}