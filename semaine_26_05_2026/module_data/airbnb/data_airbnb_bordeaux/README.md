
# 🚀 Quick Start - Airbnb Bordeaux Analysis Notebook

## 📦 Setup (5 min)

### 1. Installer les dépendances

```bash
pip install -q pandas numpy geopandas matplotlib seaborn plotly folium scikit-learn
```

### 2. Vérifier les fichiers de données

```
module_data/
├─ data_airbnb_bordeaux/
│  ├─ listings.csv          ✓ (2500+ rows)
│  ├─ neighbourhoods.csv    ✓ 
│  └─ neighbourhoods.geojson ✓
├─ Airbnb_Bordeaux_Analysis.ipynb  ← LAUNCHER
├─ USE_CASES_GUIDE.md
└─ FUTURE_IDEAS_UC8_TO_UC22.md
```

### 3. Lancer le notebook

**Option A - VS Code**:
```
Ctrl+Shift+P → "Jupyter: Open Notebook"
Select: Airbnb_Bordeaux_Analysis.ipynb
Run all: Ctrl+Shift+Enter
```

**Option B - Jupyter Lab**:
```bash
jupyter lab Airbnb_Bordeaux_Analysis.ipynb
```

**Option C - Jupyter Notebook**:
```bash
jupyter notebook Airbnb_Bordeaux_Analysis.ipynb
```

---

## ⚡ Exécution rapide

```
Cell 1:   ✓ Imports (5s)
Cell 2:   ✓ Data loading (10s)
Cell 3:   ✓ Cleaning (30s)
Cell 4:   ✓ Geo prep (20s)
Cell 5:   ✓ Use cases table (5s)
Cell 6:   ✓ KPIs + charts (15s)
Cell 7:   ✓ UC-1 Quartiers (10s)
Cell 8:   ✓ UC-2 Heatmap (15s) ← HTML output 📍
Cell 9:   ✓ UC-3 Segmentation (10s)
Cell 10:  ✓ UC-4 Superhost (10s)
Cell 11:  ✓ UC-5 Pricing (15s)
Cell 12:  ✓ UC-6 Reviews (10s)
Cell 13:  ✓ UC-7 Amenities (15s)
Cell 14:  ✓ Summary + Export (30s)
───────────────────────────────
Total:    ~150 secondes (~2.5 min)
```

---

## 📊 Résultats Attendus

Après exécution, vous aurez:

### Visualisations Générées:
- 30+ graphiques (matplotlib, plotly, folium)
- 1 carte interactive HTML
- Outputs directement dans le notebook

### Fichiers Exportés:
```
01_neighbourhood_analysis.csv      (Top quartiers)
02_segment_performance.csv         (Performance par segment)
03_amenities_impact.csv            (Impact équipements)
04_review_score_impact.csv         (Impact avis)
05_superhost_comparison.csv        (Superhost vs autres)
06_use_cases_reference.csv         (Cadrage des 7 UC)
uc2_heatmap_combined.html          (Carte interactive) 🗺️
ANALYSIS_SUMMARY.txt               (Résumé exécutif)
```

### Insights Clés:
```
✓ Top 7 quartiers rentables
✓ Segments marché optimaux  
✓ Premium Superhost: +25% revenue
✓ Sweet spot prix: ~$160/nuit
✓ Amenities impact quantifié
✓ Recommendations opérationnelles
```

---

## 🎯 Structure Logique

```
SECTION 1: Data Intake
  └─ Load CSVs + GeoJSON
     Clean & Parse (prix, %, bool, dates)
     
SECTION 2: Data Preparation
  └─ Geographic joins (spatial)
     Feature engineering
     Agregations
     
SECTION 3: Exploratory Analysis
  └─ KPIs globaux (6 charts)
     Data profiling
     
SECTION 4-13: Use Case Deep Dives (7 analyses)
  ├─ UC-1: Quartiers (choroplèthe)
  ├─ UC-2: Heatmap (density)
  ├─ UC-3: Segmentation (marché)
  ├─ UC-4: Superhost (quality)
  ├─ UC-5: Pricing (optimization)
  ├─ UC-6: Reviews (impact)
  └─ UC-7: Amenities (value)
     
SECTION 14: Insights & Export
  └─ Executive summary
     CSV exports
     Artifact generation
```

---

## 🔍 Comment Naviguer

### Pour Explorer un Use Case Spécifique:
```
1. Ouvrir: Control+F  "USE CASE X"
2. Run cells de cette section jusqu'au prochain "USE CASE"
3. Optionnel: Modifier paramètres (ex: prendre top 20 au lieu de top 10)
```

### Pour Modifier un Graphique:
```
Chaque visualisation est dans une cellule séparée
Change couleurs, labels, bins → re-run la cellule
Plotly charts = interactive (zoom, hover, export)
```

### Pour Ajouter une Nouvelle Analyse:
```
1. Créer nouvelle cellule après UC-7
2. Importer données from previous cells
3. Écrire analyse + visualisation
4. Export to CSV si nécessaire
```

---

## ⚠️ Troubleshooting

### ❌ "ModuleNotFoundError: No module named 'geopandas'"
```bash
# Solution:
pip install geopandas
# (might need dependencies: GDAL, PROJ, GEOS)
python -m pip install geopandas --upgrade
```

### ❌ "FileNotFoundError: ./data_airbnb_bordeaux/listings.csv"
```python
# Solution: Vérifier chemins
# Dans Cell 1, remplacer:
data_dir = Path('./data_airbnb_bordeaux')
# par le chemin absolu de votre dater:
data_dir = Path('c:/Users/benoi/Desktop/YNOV/semaine_26_05_2026/module_data/data_airbnb_bordeaux')
```

### ❌ "Kernel crashed / Out of memory"
```
Solution: 
- Réduire données (df.sample(0.8))
- Restart kernel: Kernel → Restart
- Check RAM: 4GB+ recommended
```

### ❌ Plotly figures pas interactive
```python
# Solution: Si offline mode
import plotly.graph_objects as go
go.Figure().show()  # should work
# Sinon: pip install plotly-orca
```

---

## 🎓 Pour Soutenance TP

### Slides Recommandées:
1. **Contexte** - Airbnb Bordeaux market, 2500+ listings
2. **Données** - Sources, cleaning, geospatial prep
3. **7 Use Cases** - 1 slide per UC (chart + insight)
4. **Recommendations** - Short/mid/long term actions
5. **Conclusion** - Key learnings + future work

### Fichiers à Montrer:
- ✅ Notebook (avec outputs)
- ✅ 6 CSV exports (data-driven)
- ✅ Heatmap HTML (interactive demo)
- ✅ Charts (export as PNG)

### Timing:
- 10 min presentation
- 5 min Q&A
- 2 min live demo (optionnel: filter une carte)

---

## 🚀 Advanced: Modifications Possibles

### Ajouter un filtre (ex: prix < $200):
```python
df_filtered = df_analysis[df_analysis['price'] < 200]
# Re-run UC-1, UC-3, UC-5 avec filtered data
```

### Comparer 2 quartiers:
```python
q1 = df_analysis[df_analysis['neighbourhood_cleansed'] == 'Centre ville (Bordeaux)']
q2 = df_analysis[df_analysis['neighbourhood_cleansed'] == 'Talence']
# Créer dashboards de comparison
```

### Créer segment custom:
```python
df_analysis['is_premium'] = (df_analysis['price'] > 200) & (df_analysis['review_scores_rating'] > 4.7)
# Analyser segment premium separately
```

---

## 📞 Besoin d'Aide?

- **Cell bloquée?** → Check error message + scroll up 
- **Visualisation pas claire?** → Hover/zoom in Plotly
- **Résultat inattendu?** → Vérifier data en Cell 3 (cleaning)
- **Want to extend?** → See `FUTURE_IDEAS_UC8_TO_UC22.md`

---

**Status**: ✅ Ready to Run  
**Estimated Time**: ~3 min execution  
**Output**: 30+ insights + 8 artifacts  

**Let's analyze! 🚀**

---
