# GA4 Google Merchandise Store — Conversion Propensity & Retargeting Analytics
<img width="2752" height="1536" alt="Info_summary" src="https://github.com/user-attachments/assets/3c5087b0-877f-494d-b0e9-44eaf7480517" />

## Project Overview
This project analyzes the **GA4 Google Merchandise Store** public dataset to identify which website sessions are most valuable for retargeting campaigns.  

Using behavioral session data from Google Analytics 4 (GA4), the project combines:
- Funnel analysis
- Cohort retention analysis
- Machine learning classification
- SHAP explainability

The objective is to help marketing teams prioritize high-intent users and improve advertising efficiency through data-driven retargeting strategies.

---

## Business Problem
E-commerce businesses spend significant budget on retargeting users, but not every visitor has equal purchase intent.

This project answers the question:

> **Which sessions are most likely to convert and therefore worth retargeting?**

The analysis identifies:
- High-intent behavioral patterns
- Funnel abandonment opportunities
- Engagement signals associated with purchases
- Predictive conversion propensity using machine learning

---

## Dataset
- **Source:** GA4 Obfuscated Sample E-commerce Dataset
- **Platform:** Google BigQuery Public Dataset
- **Period:** 2020-11-01 → 2021-01-31
- **Duration:** 92 days
- **Unit of Analysis:** Session-level

Dataset Table:
```sql
ga4_obfuscated_sample_ecommerce.events_*
```

---

## Project Objectives
- Analyze the e-commerce purchase funnel
- Measure cohort retention behavior
- Build a conversion prediction model
- Identify key conversion drivers using SHAP
- Generate actionable retargeting recommendations

---

## Key Results

| Metric | Value |
|---|---|
| Total Sessions | 360,129 |
| Conversion Rate | 1.35% |
| Purchases | 4,848 |
| Best Model | XGBoost |
| PR-AUC | 0.7308 |
| Recall @ Optimal Threshold | 89% |
| Precision @ Optimal Threshold | 62% |
| Funnel Drop-off (view → cart) | 80.2% |

---

# Purchase Funnel Analysis

The largest drop-off occurs between:

```text
view_item → add_to_cart
```

### Key Insight
Approximately **80.2%** of users who viewed a product never added it to cart.

This represents the highest-volume retargeting opportunity:
- Users already demonstrated product interest
- But did not commit to checkout

---

# Cohort Retention Analysis

### Findings
- Average Week-1 retention rate: **4.8%**
- Below the common e-commerce benchmark of **10–20%**

### Business Implication
The store has significant opportunity for:
- Re-engagement campaigns
- Email remarketing
- Display retargeting
- Push notification strategies

Recommended reactivation window:
```text
7–14 days after first session
```

---

# Machine Learning Modeling

## Models Compared
- Logistic Regression
- Random Forest
- XGBoost (Optuna-tuned)

## Why PR-AUC?
The dataset is highly imbalanced:
- Conversion rate = **1.35%**
- Imbalance ratio = **73.3 : 1**

Therefore:
- **PR-AUC** is more informative than ROC-AUC
- Better reflects real-world marketing performance

---

## Model Performance

| Model | ROC-AUC | PR-AUC | Precision | Recall | F1 |
|---|---|---|---|---|---|
| Logistic Regression | 0.9942 | 0.6723 | 0.4700 | 0.9856 | 0.6365 |
| Random Forest | 0.9958 | 0.6874 | 0.6653 | 0.6680 | 0.6667 |
| XGBoost | 0.9960 | 0.7308 | 0.5501 | 0.9969 | 0.7089 |
| XGBoost (Optimal Threshold) | 0.9960 | 0.7308 | 0.6200 | 0.8900 | 0.7315 |

### Winning Model
**XGBoost with Optuna hyperparameter tuning**

The tuned XGBoost model achieved:
- Strongest PR-AUC
- High recall on converters
- Better balance between precision and recall

---

# Feature Importance (SHAP Explainability)

SHAP values were used to explain model predictions.

## Top Predictive Features

| Rank | Feature | Mean SHAP Value | Interpretation |
|---|---|---|---|
| 1 | checkout_starts | 5.19 | Strongest purchase signal |
| 2 | total_events | 2.60 | Session engagement depth |
| 3 | session_duration_sec | 1.60 | Purchase intent proxy |

---

## Main Insight
The model behaves largely as a:

```text
Checkout-abandonment detection system
```

Users who initiate checkout but fail to purchase are the highest-value retargeting audience.

---

# Actionable Recommendations

## 1. Prioritize Checkout Abandoners
Target:
- Sessions with checkout activity
- But no purchase event

### Recommended Action
Deploy abandoned-cart reminders within 24 hours.

### Expected Impact
- High conversion uplift
- Efficient media spend allocation

---

## 2. Apply Engagement Thresholds
Exclude:
- Low-engagement sessions
- Users with minimal interaction depth

### Benefit
Reduces wasted retargeting spend while maintaining high-intent audiences.

---

## 3. Launch 7–14 Day Re-engagement Campaigns
Retention analysis suggests weak early return behavior.

### Recommendation
Implement:
- Email reactivation
- Dynamic display ads
- Push campaigns

Focused on:
```text
Week-1 non-returners
```

---

# Tech Stack

## Data & Storage
- Google BigQuery
- SQL

## Analysis & Modeling
- Python
- Pandas
- NumPy
- Scikit-learn
- XGBoost
- Optuna
- SHAP

## Visualization
- Matplotlib
- Seaborn

---

# Project Pipeline

```text
NB-01 → SQL Extraction
NB-02 → Exploratory Data Analysis
NB-03 → Feature Engineering
NB-04 → Machine Learning Models
NB-05 → Funnel Analysis
NB-06 → SHAP Explainability
NB-07 → Final Report
```

---

# Methodology

| Step | Details |
|---|---|
| Target Variable | `converted = 1` if purchase occurred |
| Split Strategy | 80/20 stratified train-test split |
| Random State | 42 |
| Imbalance Handling | scale_pos_weight / class_weight |
| Hyperparameter Tuning | Optuna (50 trials) |
| Explainability | SHAP TreeExplainer |

---

# Limitations

- Dataset limited to 92 days
- Includes Black Friday & holiday seasonality
- Obfuscated GA4 sample data
- Session-level prediction only
- Potential session leakage across users

---

# Future Improvements

- Extend to 12+ months of data
- Build user-level propensity models
- Add product-category features
- Use prospective validation windows
- Deploy real-time scoring API for marketing platforms

---

# Repository Structure

```text
├── notebooks/
│   ├── NB-01_SQL.ipynb
│   ├── NB-02_EDA.ipynb
│   ├── NB-03_Features.ipynb
│   ├── NB-04_Models.ipynb
│   ├── NB-05_Funnel.ipynb
│   ├── NB-06_SHAP.ipynb
│   └── NB-07_Report.ipynb
├── reports/
├── README.md

```

---

# Conclusion

This project demonstrates how marketing analytics and machine learning can be combined to:
- Identify high-value customer sessions
- Improve retargeting efficiency
- Reduce advertising waste
- Explain predictive behavior using interpretable AI

The final XGBoost model successfully identified likely converters with strong recall and actionable business insights, making it suitable for real-world retargeting workflows.

---

# Author

**Seiha Vat**  
Data Analyst / Data Science Portfolio Project

