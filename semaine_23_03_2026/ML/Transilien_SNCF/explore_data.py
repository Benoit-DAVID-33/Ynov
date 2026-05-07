import pandas as pd
import numpy as np
import sys, os

base = r"c:\Users\benoi\Desktop\YNOV\semaine_23_03_2026\ML\Transilien_SNCF"
X_train = pd.read_csv(os.path.join(base, 'x_train_final.csv'))
y_train = pd.read_csv(os.path.join(base, 'y_train_final.csv'))
X_test  = pd.read_csv(os.path.join(base, 'x_test_final.csv'))

sep = "="*60

# ── 1. SHAPES & COLONNES ──────────────────────────────────────────
print(sep)
print("SHAPES")
print(f"  X_train : {X_train.shape}")
print(f"  y_train : {y_train.shape}")
print(f"  X_test  : {X_test.shape}")

print(sep)
print("COLONNES X_train :")
print(list(X_train.columns))
print("COLONNES X_test :")
print(list(X_test.columns))
print("COLONNES y_train :")
print(list(y_train.columns))

# ── 2. DTYPES ───────────────────────────────────────────────────
print(sep)
print("DTYPES X_train :")
print(X_train.dtypes.to_string())

# ── 3. HEAD ──────────────────────────────────────────────────────
print(sep)
print("X_train HEAD (5) :")
print(X_train.head(5).to_string())
print("\ny_train HEAD (5) :")
print(y_train.head(5).to_string())
print("\nX_test HEAD (5) :")
print(X_test.head(5).to_string())

# ── 4. NaN par colonne ───────────────────────────────────────────
print(sep)
print("NaN X_train :")
nan_tr = X_train.isna().sum()
print(nan_tr[nan_tr > 0].to_string() if nan_tr.any() else "  Aucun NaN !")
print("NaN X_test :")
nan_te = X_test.isna().sum()
print(nan_te[nan_te > 0].to_string() if nan_te.any() else "  Aucun NaN !")
print("NaN y_train :")
nan_y = y_train.isna().sum()
print(nan_y[nan_y > 0].to_string() if nan_y.any() else "  Aucun NaN !")

# ── 5. STATS DESCRIPTIVES ────────────────────────────────────────
print(sep)
print("DESCRIBE X_train (colonnes numériques) :")
print(X_train.describe().T.to_string())

print(sep)
print("DESCRIBE y_train :")
print(y_train.describe().to_string())

# ── 6. COLONNES CATÉGORIELLES ────────────────────────────────────
print(sep)
print("Cardinalités colonnes object/string :")
for col in X_train.select_dtypes(include=['object']).columns:
    n = X_train[col].nunique()
    print(f"  {col:20s} : {n} valeurs uniques  ex: {X_train[col].unique()[:5]}")

# ── 7. Vérif colonne 'train' présente ? ─────────────────────────
print(sep)
print("Colonne 'train' dans X_train :", 'train' in X_train.columns)
print("Colonne 'train' dans X_test  :", 'train' in X_test.columns)

# ── 8. Doublons ─────────────────────────────────────────────────
print(sep)
print(f"Doublons X_train : {X_train.duplicated().sum()}")
print(f"Doublons X_test  : {X_test.duplicated().sum()}")

# ── 9. Target distribution détaillée ────────────────────────────
print(sep)
print("Distribution cible p0q0 :")
vc = y_train['p0q0'].value_counts().sort_index()
print(vc.to_string())
pct_zero = (y_train['p0q0'] == 0).mean()
pct_neg  = (y_train['p0q0'] < 0).mean()
pct_pos  = (y_train['p0q0'] > 0).mean()
print(f"\n  == 0 : {pct_zero:.1%}  |  < 0 : {pct_neg:.1%}  |  > 0 : {pct_pos:.1%}")

# ── 10. Cohérence index X_test vs y_sample ─────────────────────
print(sep)
try:
    y_sample = pd.read_csv(os.path.join(base, 'y_sample_final.csv'))
    print("y_sample colonnes :", list(y_sample.columns))
    print(y_sample.head())
    print(f"X_test index max={X_test.index.max()}  y_sample rows={len(y_sample)}")
except Exception as e:
    print(f"y_sample: {e}")

# ── 11. Lags disponibles dans train vs test ──────────────────────
print(sep)
lag_cols = [c for c in X_train.columns if c.startswith('p')]
print(f"Lag columns: {lag_cols}")
print("NaN lags X_train :")
print(X_train[lag_cols].isna().sum().to_string())
print("NaN lags X_test :")
print(X_test[lag_cols].isna().sum().to_string())

# ── 12. Corrélation lags → cible ────────────────────────────────
print(sep)
print("Corrélation lags -> p0q0 :")
tmp = X_train[lag_cols].copy()
tmp['p0q0'] = y_train['p0q0']
print(tmp.corr()['p0q0'].drop('p0q0').sort_values(ascending=False).to_string())

# ── 13. Vérif calculs du FE dans master_ia_v2 ────────────────────────────────
print(sep)
print("Vérif feature engineering :")
backward = ['p2q0', 'p3q0', 'p4q0']
lateral  = ['p0q2', 'p0q3', 'p0q4']
all_lags = backward + lateral
# les colonnes backward/lateral sont-elles bien dans X_train ?
for c in all_lags:
    present = c in X_train.columns
    n_nan   = X_train[c].isna().sum() if present else "N/A"
    print(f"  {c}: present={present}  NaN={n_nan}")

# range_backward : max des backward - min des backward (pas max_lag!)
# Le code fait:
#   max_lag = all_lags.max   → OK
#   range_backward = max_lag.clip(lower=backward.max) - backward.min
# C'est bizarre — vérifions
print("\nVérif 'range_backward' calcul :")
print("  Code actuel : max_lag.clip(lower=backward.max) - backward.min")
print("  Ce que ça vaut (5 ex) :")
df = X_train[all_lags].head(5).copy()
df['max_lag']        = df[all_lags].max(axis=1)
df['range_backward_current'] = df['max_lag'].clip(lower=df[backward].max(axis=1)) - df[backward].min(axis=1)
df['range_backward_correct'] = df[backward].max(axis=1) - df[backward].min(axis=1)
df['diff'] = df['range_backward_current'] - df['range_backward_correct']
print(df[['max_lag','range_backward_current','range_backward_correct','diff']].to_string())

print(sep)
print("FIN EXPLORATION")
