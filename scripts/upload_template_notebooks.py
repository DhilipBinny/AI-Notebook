"""Upload full notebook content for seeded templates to S3."""
import json
import boto3

s3 = boto3.client(
    "s3",
    endpoint_url="http://ainotebook-minio:9000",
    aws_access_key_id="minioadmin",
    aws_secret_access_key="minioadmin123",
    region_name="us-east-1",
)
BUCKET = "notebooks"

meta = {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}}

def mk(cells):
    return {"nbformat": 4, "nbformat_minor": 5, "metadata": meta, "cells": cells}

def md(src):
    return {"cell_type": "markdown", "metadata": {}, "source": src}

def code(src):
    return {"cell_type": "code", "metadata": {}, "source": src, "outputs": [], "execution_count": None}


# Get template IDs from DB
import pymysql
conn = pymysql.connect(host="ainotebook-mysql", port=3306, user="root",
                       password="ainotebook_dev_password", database="ainotebook")
cursor = conn.cursor()
cursor.execute("SELECT id, name, storage_path FROM notebook_templates")
rows = cursor.fetchall()
name_to_info = {r[1]: {"id": r[0], "path": r[2]} for r in rows}
cursor.close()
conn.close()


NOTEBOOKS = {
    "Python Basics": mk([
        md("# Python Basics\n\nWelcome! This notebook covers the fundamentals of Python programming.\n\n**Topics:** Variables, data types, strings, lists, dictionaries, control flow, functions"),
        md("## 1. Variables and Data Types"),
        code("# Numbers\nage = 25\npi = 3.14159\n\n# Strings\nname = \"Alice\"\ngreeting = f\"Hello, {name}! You are {age} years old.\"\n\n# Boolean\nis_student = True\n\nprint(greeting)\nprint(f\"Type of age: {type(age)}\")\nprint(f\"Type of pi: {type(pi)}\")\nprint(f\"Type of name: {type(name)}\")"),
        md("## 2. Lists and Dictionaries"),
        code("# Lists - ordered, mutable\nfruits = [\"apple\", \"banana\", \"cherry\"]\nfruits.append(\"date\")\nprint(f\"Fruits: {fruits}\")\nprint(f\"First: {fruits[0]}, Last: {fruits[-1]}\")\n\n# List comprehension\nsquares = [x**2 for x in range(1, 6)]\nprint(f\"Squares: {squares}\")"),
        code("# Dictionaries - key-value pairs\nstudent = {\n    \"name\": \"Alice\",\n    \"age\": 25,\n    \"grades\": [90, 85, 92]\n}\n\nprint(f\"Name: {student['name']}\")\nprint(f\"Average grade: {sum(student['grades']) / len(student['grades']):.1f}\")\n\nfor key, value in student.items():\n    print(f\"  {key}: {value}\")"),
        md("## 3. Control Flow"),
        code("# If/else\nscore = 85\nif score >= 90:\n    grade = \"A\"\nelif score >= 80:\n    grade = \"B\"\nelif score >= 70:\n    grade = \"C\"\nelse:\n    grade = \"F\"\nprint(f\"Score {score} = Grade {grade}\")\n\n# For loop\nfor i in range(5):\n    print(f\"  Count: {i}\")\n\n# While loop\ncount = 0\nwhile count < 3:\n    print(f\"  While: {count}\")\n    count += 1"),
        md("## 4. Functions"),
        code("def calculate_bmi(weight_kg, height_m):\n    \"\"\"Calculate Body Mass Index.\"\"\"\n    bmi = weight_kg / (height_m ** 2)\n    if bmi < 18.5: category = \"Underweight\"\n    elif bmi < 25: category = \"Normal\"\n    elif bmi < 30: category = \"Overweight\"\n    else: category = \"Obese\"\n    return bmi, category\n\nbmi, category = calculate_bmi(70, 1.75)\nprint(f\"BMI: {bmi:.1f} ({category})\")"),
        md("## Next Steps\n\nTry modifying the code cells above and running them! Use the AI assistant to ask questions about any concept."),
    ]),

    "Data Analysis with Pandas": mk([
        md("# Data Analysis with Pandas\n\nPandas is the go-to library for data manipulation in Python.\n\n**Topics:** DataFrames, filtering, grouping, aggregation, statistics"),
        code("import pandas as pd\nimport numpy as np\n\nprint(f\"Pandas version: {pd.__version__}\")"),
        md("## 1. Creating DataFrames"),
        code("np.random.seed(42)\n\ndata = {\n    'name': ['Alice', 'Bob', 'Charlie', 'Diana', 'Eve', 'Frank', 'Grace', 'Henry'],\n    'department': ['Engineering', 'Marketing', 'Engineering', 'Marketing', 'Engineering', 'HR', 'HR', 'Engineering'],\n    'salary': np.random.randint(50000, 120000, 8),\n    'years_experience': np.random.randint(1, 15, 8),\n    'performance_score': np.round(np.random.uniform(3.0, 5.0, 8), 1)\n}\n\ndf = pd.DataFrame(data)\ndf"),
        md("## 2. Exploring the Data"),
        code("print(\"Shape:\", df.shape)\nprint(\"\\nColumn types:\")\nprint(df.dtypes)\nprint(\"\\nBasic statistics:\")\ndf.describe()"),
        md("## 3. Filtering and Selecting"),
        code("# High performers in Engineering\nhigh_performers = df[(df['department'] == 'Engineering') & (df['performance_score'] >= 4.0)]\nprint(\"High-performing engineers:\")\nprint(high_performers[['name', 'salary', 'performance_score']])\n\nprint(\"\\nSorted by salary:\")\nprint(df[['name', 'salary']].sort_values('salary', ascending=False))"),
        md("## 4. Grouping and Aggregation"),
        code("dept_stats = df.groupby('department').agg({\n    'salary': ['mean', 'min', 'max'],\n    'years_experience': 'mean',\n    'performance_score': 'mean',\n    'name': 'count'\n}).round(1)\n\ndept_stats.columns = ['avg_salary', 'min_salary', 'max_salary', 'avg_exp', 'avg_perf', 'headcount']\nprint(\"Department Statistics:\")\ndept_stats"),
        code("# Computed columns\ndf['salary_per_year'] = (df['salary'] / df['years_experience']).round(0)\ndf['is_senior'] = df['years_experience'] >= 5\ndf[['name', 'salary', 'years_experience', 'salary_per_year', 'is_senior']]"),
        md("## Next Steps\n\n- Try `pd.read_csv('your_file.csv')` to load your own data\n- Explore `df.plot()` for quick visualizations"),
    ]),

    "Data Visualization": mk([
        md("# Data Visualization\n\nCreate compelling charts with matplotlib and seaborn.\n\n**Charts:** Line, bar, scatter, histogram, heatmap"),
        code("import matplotlib.pyplot as plt\nimport seaborn as sns\nimport numpy as np\nimport pandas as pd\n\nsns.set_theme(style='whitegrid')\nprint('Libraries loaded!')"),
        md("## 1. Line Chart"),
        code("months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']\nnp.random.seed(42)\nsales_2024 = np.cumsum(np.random.randint(10, 50, 12)) + 100\nsales_2025 = np.cumsum(np.random.randint(15, 55, 12)) + 120\n\nfig, ax = plt.subplots(figsize=(10, 5))\nax.plot(months, sales_2024, marker='o', label='2024', linewidth=2)\nax.plot(months, sales_2025, marker='s', label='2025', linewidth=2)\nax.set_title('Monthly Cumulative Sales', fontsize=14, fontweight='bold')\nax.set_xlabel('Month')\nax.set_ylabel('Sales ($K)')\nax.legend()\nplt.tight_layout()\nplt.show()"),
        md("## 2. Bar Plot"),
        code("departments = ['Engineering', 'Marketing', 'Sales', 'HR', 'Finance']\nq1 = [4.2, 3.8, 4.5, 3.9, 4.1]\nq2 = [4.4, 4.0, 4.3, 4.2, 4.0]\n\nx = np.arange(len(departments))\nw = 0.35\n\nfig, ax = plt.subplots(figsize=(10, 5))\nb1 = ax.bar(x - w/2, q1, w, label='Q1', color='#4F86C6')\nb2 = ax.bar(x + w/2, q2, w, label='Q2', color='#F28C38')\nax.set_ylabel('Performance Score')\nax.set_title('Department Performance by Quarter', fontsize=14, fontweight='bold')\nax.set_xticks(x)\nax.set_xticklabels(departments)\nax.legend()\nax.set_ylim(3.5, 5.0)\nax.bar_label(b1, fmt='%.1f', padding=3)\nax.bar_label(b2, fmt='%.1f', padding=3)\nplt.tight_layout()\nplt.show()"),
        md("## 3. Scatter Plot with Regression"),
        code("np.random.seed(42)\nn = 50\nhours = np.random.uniform(1, 10, n)\nscores = 40 + 5 * hours + np.random.normal(0, 5, n)\nscores = np.clip(scores, 0, 100)\ndf_s = pd.DataFrame({'Study Hours': hours, 'Exam Score': scores})\n\nfig, ax = plt.subplots(figsize=(8, 6))\nsns.regplot(data=df_s, x='Study Hours', y='Exam Score', ax=ax,\n            scatter_kws={'alpha': 0.6, 's': 60}, line_kws={'color': 'red', 'linewidth': 2})\nax.set_title('Study Hours vs Exam Score', fontsize=14, fontweight='bold')\ncorr = df_s['Study Hours'].corr(df_s['Exam Score'])\nax.text(0.05, 0.95, f'r = {corr:.2f}', transform=ax.transAxes, fontsize=12,\n        verticalalignment='top', bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))\nplt.tight_layout()\nplt.show()"),
        md("## 4. Heatmap"),
        code("np.random.seed(42)\ndf_h = pd.DataFrame({'Revenue': np.random.randn(100), 'Marketing': np.random.randn(100),\n    'Customers': np.random.randn(100), 'Satisfaction': np.random.randn(100)})\ndf_h['Revenue'] += df_h['Marketing'] * 0.6 + df_h['Customers'] * 0.4\ndf_h['Satisfaction'] += df_h['Customers'] * 0.3\n\nfig, ax = plt.subplots(figsize=(7, 5))\nsns.heatmap(df_h.corr(), annot=True, cmap='coolwarm', center=0, fmt='.2f', square=True, ax=ax)\nax.set_title('Correlation Matrix', fontsize=14, fontweight='bold')\nplt.tight_layout()\nplt.show()"),
        md("## Next Steps\n\n- Customize colors, labels, and styles\n- Try `plotly` for interactive charts"),
    ]),

    "API Data Fetching": mk([
        md("# API Data Fetching\n\nLearn to work with REST APIs to fetch and process data.\n\n**Topics:** GET/POST requests, JSON parsing, error handling, pandas integration"),
        code("import requests\nimport json\nimport pandas as pd\nprint('Libraries loaded!')"),
        md("## 1. Basic GET Request"),
        code("response = requests.get('https://jsonplaceholder.typicode.com/posts', params={'_limit': 5})\nprint(f'Status: {response.status_code}')\n\nposts = response.json()\nfor post in posts:\n    print(f\"\\n[{post['id']}] {post['title'][:60]}\")"),
        md("## 2. JSON to DataFrame"),
        code("response = requests.get('https://jsonplaceholder.typicode.com/users')\nusers = response.json()\n\ndf = pd.json_normalize(users, sep='_')\ndf[['name', 'email', 'company_name', 'address_city']]"),
        md("## 3. Error Handling"),
        code("def safe_get(url, params=None, timeout=10):\n    try:\n        response = requests.get(url, params=params, timeout=timeout)\n        response.raise_for_status()\n        return response.json()\n    except requests.exceptions.Timeout:\n        print(f'Timeout: {url}')\n    except requests.exceptions.HTTPError as e:\n        print(f'HTTP error: {e.response.status_code}')\n    except requests.exceptions.ConnectionError:\n        print(f'Connection failed: {url}')\n    return None\n\ndata = safe_get('https://jsonplaceholder.typicode.com/posts/1')\nif data:\n    print(f\"Title: {data['title']}\")\n\nsafe_get('https://jsonplaceholder.typicode.com/invalid')"),
        md("## 4. POST Request"),
        code("new_post = {'title': 'My API Post', 'body': 'Created via API', 'userId': 1}\n\nresponse = requests.post('https://jsonplaceholder.typicode.com/posts',\n    json=new_post, headers={'Accept': 'application/json'})\n\nprint(f'Status: {response.status_code}')\nprint(f'Created: {json.dumps(response.json(), indent=2)}')"),
        md("## Next Steps\n\n- Try other public APIs (GitHub, weather, etc.)\n- Add authentication headers for protected APIs"),
    ]),

    "Machine Learning Starter": mk([
        md("# Machine Learning Starter\n\nBuild your first ML model using scikit-learn.\n\n**Topics:** Data loading, train/test split, model training, evaluation, predictions"),
        code("import numpy as np\nimport pandas as pd\nimport matplotlib.pyplot as plt\nimport seaborn as sns\nfrom sklearn.datasets import load_iris\nfrom sklearn.model_selection import train_test_split\nfrom sklearn.preprocessing import StandardScaler\nfrom sklearn.ensemble import RandomForestClassifier\nfrom sklearn.metrics import classification_report, confusion_matrix, accuracy_score\n\nsns.set_theme(style='whitegrid')\nprint('Libraries loaded!')"),
        md("## 1. Load and Explore Data"),
        code("iris = load_iris()\ndf = pd.DataFrame(iris.data, columns=iris.feature_names)\ndf['species'] = pd.Categorical.from_codes(iris.target, iris.target_names)\n\nprint(f'Shape: {df.shape}')\nprint(f'Classes: {list(iris.target_names)}')\nprint(f'\\nSamples per class:')\nprint(df['species'].value_counts())\ndf.head()"),
        code("fig, axes = plt.subplots(2, 2, figsize=(12, 8))\nfor i, col in enumerate(iris.feature_names):\n    ax = axes[i // 2][i % 2]\n    for species in iris.target_names:\n        subset = df[df['species'] == species]\n        ax.hist(subset[col], alpha=0.6, label=species, bins=15)\n    ax.set_title(col)\n    ax.legend()\nplt.suptitle('Feature Distributions by Species', fontsize=14, fontweight='bold')\nplt.tight_layout()\nplt.show()"),
        md("## 2. Prepare Data"),
        code("X = df[iris.feature_names].values\ny = iris.target\n\nX_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)\n\nscaler = StandardScaler()\nX_train_scaled = scaler.fit_transform(X_train)\nX_test_scaled = scaler.transform(X_test)\n\nprint(f'Training: {X_train.shape[0]} samples')\nprint(f'Test: {X_test.shape[0]} samples')"),
        md("## 3. Train Model"),
        code("model = RandomForestClassifier(n_estimators=100, max_depth=3, random_state=42)\nmodel.fit(X_train_scaled, y_train)\n\nimportance = pd.Series(model.feature_importances_, index=iris.feature_names).sort_values(ascending=False)\nprint('Feature Importance:')\nfor feat, imp in importance.items():\n    print(f'  {feat}: {imp:.3f}')"),
        md("## 4. Evaluate Model"),
        code("y_pred = model.predict(X_test_scaled)\n\nprint(f'Accuracy: {accuracy_score(y_test, y_pred):.2%}')\nprint(f'\\nClassification Report:')\nprint(classification_report(y_test, y_pred, target_names=iris.target_names))\n\nfig, ax = plt.subplots(figsize=(7, 5))\ncm = confusion_matrix(y_test, y_pred)\nsns.heatmap(cm, annot=True, fmt='d', cmap='Blues',\n            xticklabels=iris.target_names, yticklabels=iris.target_names, ax=ax)\nax.set_xlabel('Predicted')\nax.set_ylabel('Actual')\nax.set_title('Confusion Matrix', fontsize=14, fontweight='bold')\nplt.tight_layout()\nplt.show()"),
        md("## Next Steps\n\n- Try `SVC`, `KNeighborsClassifier`, `GradientBoostingClassifier`\n- Use `GridSearchCV` for hyperparameter tuning\n- Load your own dataset with `pd.read_csv()`"),
    ]),
}


for name, nb in NOTEBOOKS.items():
    if name not in name_to_info:
        print(f"  [!] {name} not found in DB, skipping")
        continue
    path = name_to_info[name]["path"]
    s3.put_object(
        Bucket=BUCKET,
        Key=path,
        Body=json.dumps(nb, indent=2).encode("utf-8"),
        ContentType="application/json",
    )
    print(f"  [+] {name}: {len(nb['cells'])} cells -> {path}")

print(f"\nDone! Uploaded {len(NOTEBOOKS)} notebooks.")
