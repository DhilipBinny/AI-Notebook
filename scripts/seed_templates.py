#!/usr/bin/env python3
"""
Seed sample notebook templates into DB + S3.

Usage:
    python3 scripts/seed_templates.py

Requires: pip install boto3 mysql-connector-python
"""

import json
import uuid
import boto3
import mysql.connector
from datetime import datetime

# Config
DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 3306,
    "user": "root",
    "password": "ainotebook_dev_password",
    "database": "ainotebook",
}

S3_CONFIG = {
    "endpoint_url": "http://localhost:9002",
    "aws_access_key_id": "minioadmin",
    "aws_secret_access_key": "minioadmin123",
}
S3_BUCKET = "notebooks"

# Admin user ID (dhilip@echoltech.com)
ADMIN_USER_ID = "7d77c5c4-81d2-465c-9c4c-63ec9988aa62"

# ─── Template definitions ───────────────────────────────────────────────

TEMPLATES = [
    {
        "name": "Python Basics",
        "description": "Learn Python fundamentals: variables, data types, loops, functions, and basic I/O. Great for absolute beginners.",
        "category": "Learning",
        "difficulty_level": "beginner",
        "estimated_minutes": 30,
        "tags": ["python", "basics", "tutorial"],
        "is_public": True,
        "sort_order": 1,
        "notebook": {
            "nbformat": 4,
            "nbformat_minor": 5,
            "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
            "cells": [
                {"cell_type": "markdown", "metadata": {}, "source": "# Python Basics\n\nWelcome! This notebook covers the fundamentals of Python programming.\n\n**Topics covered:**\n- Variables and data types\n- Strings and string operations\n- Lists, tuples, and dictionaries\n- Control flow (if/else, loops)\n- Functions\n- Basic I/O"},
                {"cell_type": "markdown", "metadata": {}, "source": "## 1. Variables and Data Types\n\nPython is dynamically typed - you don't need to declare variable types."},
                {"cell_type": "code", "metadata": {}, "source": "# Numbers\nage = 25\npi = 3.14159\n\n# Strings\nname = \"Alice\"\ngreeting = f\"Hello, {name}! You are {age} years old.\"\n\n# Boolean\nis_student = True\n\nprint(greeting)\nprint(f\"Type of age: {type(age)}\")\nprint(f\"Type of pi: {type(pi)}\")\nprint(f\"Type of name: {type(name)}\")\nprint(f\"Type of is_student: {type(is_student)}\")", "outputs": [], "execution_count": None},
                {"cell_type": "markdown", "metadata": {}, "source": "## 2. Lists and Dictionaries"},
                {"cell_type": "code", "metadata": {}, "source": "# Lists - ordered, mutable\nfruits = [\"apple\", \"banana\", \"cherry\"]\nfruits.append(\"date\")\nprint(f\"Fruits: {fruits}\")\nprint(f\"First fruit: {fruits[0]}\")\nprint(f\"Last fruit: {fruits[-1]}\")\n\n# List comprehension\nsquares = [x**2 for x in range(1, 6)]\nprint(f\"Squares: {squares}\")", "outputs": [], "execution_count": None},
                {"cell_type": "code", "metadata": {}, "source": "# Dictionaries - key-value pairs\nstudent = {\n    \"name\": \"Alice\",\n    \"age\": 25,\n    \"grades\": [90, 85, 92]\n}\n\nprint(f\"Name: {student['name']}\")\nprint(f\"Average grade: {sum(student['grades']) / len(student['grades']):.1f}\")\n\n# Iterating\nfor key, value in student.items():\n    print(f\"  {key}: {value}\")", "outputs": [], "execution_count": None},
                {"cell_type": "markdown", "metadata": {}, "source": "## 3. Control Flow"},
                {"cell_type": "code", "metadata": {}, "source": "# If/else\nscore = 85\n\nif score >= 90:\n    grade = \"A\"\nelif score >= 80:\n    grade = \"B\"\nelif score >= 70:\n    grade = \"C\"\nelse:\n    grade = \"F\"\n\nprint(f\"Score {score} = Grade {grade}\")\n\n# For loop\nfor i in range(5):\n    print(f\"  Count: {i}\")\n\n# While loop\ncount = 0\nwhile count < 3:\n    print(f\"  While count: {count}\")\n    count += 1", "outputs": [], "execution_count": None},
                {"cell_type": "markdown", "metadata": {}, "source": "## 4. Functions"},
                {"cell_type": "code", "metadata": {}, "source": "def calculate_bmi(weight_kg, height_m):\n    \"\"\"Calculate Body Mass Index.\"\"\"\n    bmi = weight_kg / (height_m ** 2)\n    if bmi < 18.5:\n        category = \"Underweight\"\n    elif bmi < 25:\n        category = \"Normal\"\n    elif bmi < 30:\n        category = \"Overweight\"\n    else:\n        category = \"Obese\"\n    return bmi, category\n\nbmi, category = calculate_bmi(70, 1.75)\nprint(f\"BMI: {bmi:.1f} ({category})\")", "outputs": [], "execution_count": None},
                {"cell_type": "markdown", "metadata": {}, "source": "## Next Steps\n\nTry modifying the code cells above and running them!\n\n- Change variable values and see what happens\n- Add new items to the lists\n- Write your own functions\n- Use the AI assistant (click the sparkle icon) to ask questions about any concept"},
            ],
        },
    },
    {
        "name": "Data Analysis with Pandas",
        "description": "Introduction to data analysis using pandas: DataFrames, filtering, grouping, and basic statistics.",
        "category": "Data Science",
        "difficulty_level": "beginner",
        "estimated_minutes": 45,
        "tags": ["pandas", "data-analysis", "dataframe"],
        "is_public": True,
        "sort_order": 2,
        "notebook": {
            "nbformat": 4,
            "nbformat_minor": 5,
            "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
            "cells": [
                {"cell_type": "markdown", "metadata": {}, "source": "# Data Analysis with Pandas\n\nPandas is the go-to library for data manipulation in Python.\n\n**Topics covered:**\n- Creating DataFrames\n- Reading/writing data\n- Filtering and selecting data\n- Grouping and aggregation\n- Basic statistics"},
                {"cell_type": "code", "metadata": {}, "source": "import pandas as pd\nimport numpy as np\n\nprint(f\"Pandas version: {pd.__version__}\")", "outputs": [], "execution_count": None},
                {"cell_type": "markdown", "metadata": {}, "source": "## 1. Creating DataFrames"},
                {"cell_type": "code", "metadata": {}, "source": "# Create a sample dataset\nnp.random.seed(42)\n\ndata = {\n    'name': ['Alice', 'Bob', 'Charlie', 'Diana', 'Eve', 'Frank', 'Grace', 'Henry'],\n    'department': ['Engineering', 'Marketing', 'Engineering', 'Marketing', 'Engineering', 'HR', 'HR', 'Engineering'],\n    'salary': np.random.randint(50000, 120000, 8),\n    'years_experience': np.random.randint(1, 15, 8),\n    'performance_score': np.round(np.random.uniform(3.0, 5.0, 8), 1)\n}\n\ndf = pd.DataFrame(data)\ndf", "outputs": [], "execution_count": None},
                {"cell_type": "markdown", "metadata": {}, "source": "## 2. Exploring the Data"},
                {"cell_type": "code", "metadata": {}, "source": "# Basic info\nprint(\"Shape:\", df.shape)\nprint(\"\\nColumn types:\")\nprint(df.dtypes)\nprint(\"\\nBasic statistics:\")\ndf.describe()", "outputs": [], "execution_count": None},
                {"cell_type": "markdown", "metadata": {}, "source": "## 3. Filtering and Selecting"},
                {"cell_type": "code", "metadata": {}, "source": "# Filter: high performers in Engineering\nhigh_performers = df[(df['department'] == 'Engineering') & (df['performance_score'] >= 4.0)]\nprint(\"High-performing engineers:\")\nprint(high_performers[['name', 'salary', 'performance_score']])\n\n# Select specific columns\nprint(\"\\nNames and salaries:\")\nprint(df[['name', 'salary']].sort_values('salary', ascending=False))", "outputs": [], "execution_count": None},
                {"cell_type": "markdown", "metadata": {}, "source": "## 4. Grouping and Aggregation"},
                {"cell_type": "code", "metadata": {}, "source": "# Group by department\ndept_stats = df.groupby('department').agg({\n    'salary': ['mean', 'min', 'max'],\n    'years_experience': 'mean',\n    'performance_score': 'mean',\n    'name': 'count'\n}).round(1)\n\ndept_stats.columns = ['avg_salary', 'min_salary', 'max_salary', 'avg_experience', 'avg_performance', 'headcount']\nprint(\"Department Statistics:\")\ndept_stats", "outputs": [], "execution_count": None},
                {"cell_type": "code", "metadata": {}, "source": "# Add computed columns\ndf['salary_per_year_exp'] = (df['salary'] / df['years_experience']).round(0)\ndf['is_senior'] = df['years_experience'] >= 5\n\nprint(\"Updated DataFrame:\")\ndf[['name', 'salary', 'years_experience', 'salary_per_year_exp', 'is_senior']]", "outputs": [], "execution_count": None},
                {"cell_type": "markdown", "metadata": {}, "source": "## Next Steps\n\n- Try loading your own CSV: `pd.read_csv('your_file.csv')`\n- Explore `df.plot()` for quick visualizations\n- Use the AI assistant to help with complex queries"},
            ],
        },
    },
    {
        "name": "Data Visualization",
        "description": "Create charts and plots with matplotlib and seaborn: line charts, bar plots, scatter plots, and heatmaps.",
        "category": "Data Science",
        "difficulty_level": "beginner",
        "estimated_minutes": 40,
        "tags": ["matplotlib", "seaborn", "visualization", "charts"],
        "is_public": True,
        "sort_order": 3,
        "notebook": {
            "nbformat": 4,
            "nbformat_minor": 5,
            "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
            "cells": [
                {"cell_type": "markdown", "metadata": {}, "source": "# Data Visualization\n\nLearn to create compelling visualizations with matplotlib and seaborn.\n\n**Charts covered:**\n- Line charts\n- Bar plots\n- Scatter plots\n- Histograms\n- Heatmaps"},
                {"cell_type": "code", "metadata": {}, "source": "import matplotlib.pyplot as plt\nimport seaborn as sns\nimport numpy as np\nimport pandas as pd\n\n# Set style\nsns.set_theme(style=\"whitegrid\")\nprint(\"Libraries loaded!\")", "outputs": [], "execution_count": None},
                {"cell_type": "markdown", "metadata": {}, "source": "## 1. Line Chart"},
                {"cell_type": "code", "metadata": {}, "source": "# Simulate monthly sales data\nmonths = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']\nnp.random.seed(42)\nsales_2024 = np.cumsum(np.random.randint(10, 50, 12)) + 100\nsales_2025 = np.cumsum(np.random.randint(15, 55, 12)) + 120\n\nfig, ax = plt.subplots(figsize=(10, 5))\nax.plot(months, sales_2024, marker='o', label='2024', linewidth=2)\nax.plot(months, sales_2025, marker='s', label='2025', linewidth=2)\nax.set_title('Monthly Cumulative Sales', fontsize=14, fontweight='bold')\nax.set_xlabel('Month')\nax.set_ylabel('Sales ($K)')\nax.legend()\nax.grid(True, alpha=0.3)\nplt.tight_layout()\nplt.show()", "outputs": [], "execution_count": None},
                {"cell_type": "markdown", "metadata": {}, "source": "## 2. Bar Plot"},
                {"cell_type": "code", "metadata": {}, "source": "# Department performance comparison\ndepartments = ['Engineering', 'Marketing', 'Sales', 'HR', 'Finance']\nq1_scores = [4.2, 3.8, 4.5, 3.9, 4.1]\nq2_scores = [4.4, 4.0, 4.3, 4.2, 4.0]\n\nx = np.arange(len(departments))\nwidth = 0.35\n\nfig, ax = plt.subplots(figsize=(10, 5))\nbars1 = ax.bar(x - width/2, q1_scores, width, label='Q1', color='#4F86C6')\nbars2 = ax.bar(x + width/2, q2_scores, width, label='Q2', color='#F28C38')\nax.set_ylabel('Performance Score')\nax.set_title('Department Performance by Quarter', fontsize=14, fontweight='bold')\nax.set_xticks(x)\nax.set_xticklabels(departments)\nax.legend()\nax.set_ylim(3.5, 5.0)\nax.bar_label(bars1, fmt='%.1f', padding=3)\nax.bar_label(bars2, fmt='%.1f', padding=3)\nplt.tight_layout()\nplt.show()", "outputs": [], "execution_count": None},
                {"cell_type": "markdown", "metadata": {}, "source": "## 3. Scatter Plot with Regression"},
                {"cell_type": "code", "metadata": {}, "source": "# Generate correlated data\nnp.random.seed(42)\nn = 50\nstudy_hours = np.random.uniform(1, 10, n)\nexam_score = 40 + 5 * study_hours + np.random.normal(0, 5, n)\nexam_score = np.clip(exam_score, 0, 100)\n\ndf_scatter = pd.DataFrame({'Study Hours': study_hours, 'Exam Score': exam_score})\n\nfig, ax = plt.subplots(figsize=(8, 6))\nsns.regplot(data=df_scatter, x='Study Hours', y='Exam Score', ax=ax,\n            scatter_kws={'alpha': 0.6, 's': 60},\n            line_kws={'color': 'red', 'linewidth': 2})\nax.set_title('Study Hours vs Exam Score', fontsize=14, fontweight='bold')\ncorr = df_scatter['Study Hours'].corr(df_scatter['Exam Score'])\nax.text(0.05, 0.95, f'r = {corr:.2f}', transform=ax.transAxes,\n        fontsize=12, verticalalignment='top',\n        bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))\nplt.tight_layout()\nplt.show()", "outputs": [], "execution_count": None},
                {"cell_type": "markdown", "metadata": {}, "source": "## 4. Heatmap"},
                {"cell_type": "code", "metadata": {}, "source": "# Correlation heatmap\nnp.random.seed(42)\ndf_heat = pd.DataFrame({\n    'Revenue': np.random.randn(100),\n    'Marketing Spend': np.random.randn(100),\n    'Customer Count': np.random.randn(100),\n    'Satisfaction': np.random.randn(100),\n    'Employee Count': np.random.randn(100),\n})\n# Add some correlations\ndf_heat['Revenue'] += df_heat['Marketing Spend'] * 0.6 + df_heat['Customer Count'] * 0.4\ndf_heat['Satisfaction'] += df_heat['Employee Count'] * 0.3\n\ncorr_matrix = df_heat.corr()\n\nfig, ax = plt.subplots(figsize=(8, 6))\nsns.heatmap(corr_matrix, annot=True, cmap='coolwarm', center=0,\n            fmt='.2f', square=True, ax=ax,\n            linewidths=0.5, linecolor='white')\nax.set_title('Correlation Matrix', fontsize=14, fontweight='bold')\nplt.tight_layout()\nplt.show()", "outputs": [], "execution_count": None},
                {"cell_type": "markdown", "metadata": {}, "source": "## Next Steps\n\n- Try customizing colors, labels, and styles\n- Explore `plt.subplot()` for multi-panel figures\n- Check out `plotly` for interactive charts"},
            ],
        },
    },
    {
        "name": "API Data Fetching",
        "description": "Learn to fetch and process data from REST APIs using the requests library. Includes JSON parsing and error handling.",
        "category": "Web & APIs",
        "difficulty_level": "intermediate",
        "estimated_minutes": 35,
        "tags": ["api", "requests", "json", "web"],
        "is_public": True,
        "sort_order": 4,
        "notebook": {
            "nbformat": 4,
            "nbformat_minor": 5,
            "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
            "cells": [
                {"cell_type": "markdown", "metadata": {}, "source": "# API Data Fetching\n\nLearn to work with REST APIs to fetch and process data.\n\n**Topics covered:**\n- Making GET/POST requests\n- JSON parsing\n- Error handling\n- Pagination\n- Working with API responses in pandas"},
                {"cell_type": "code", "metadata": {}, "source": "import requests\nimport json\nimport pandas as pd\n\nprint(\"Libraries loaded!\")", "outputs": [], "execution_count": None},
                {"cell_type": "markdown", "metadata": {}, "source": "## 1. Basic GET Request"},
                {"cell_type": "code", "metadata": {}, "source": "# Fetch data from a public API\nresponse = requests.get('https://jsonplaceholder.typicode.com/posts', params={'_limit': 5})\n\nprint(f\"Status: {response.status_code}\")\nprint(f\"Content-Type: {response.headers.get('content-type')}\")\n\nposts = response.json()\nfor post in posts:\n    print(f\"\\n[{post['id']}] {post['title'][:60]}\")", "outputs": [], "execution_count": None},
                {"cell_type": "markdown", "metadata": {}, "source": "## 2. JSON to DataFrame"},
                {"cell_type": "code", "metadata": {}, "source": "# Convert API response to DataFrame\nresponse = requests.get('https://jsonplaceholder.typicode.com/users')\nusers = response.json()\n\n# Flatten nested JSON\ndf = pd.json_normalize(users, sep='_')\nprint(f\"Columns: {list(df.columns)}\\n\")\ndf[['name', 'email', 'company_name', 'address_city']]", "outputs": [], "execution_count": None},
                {"cell_type": "markdown", "metadata": {}, "source": "## 3. Error Handling"},
                {"cell_type": "code", "metadata": {}, "source": "def safe_get(url, params=None, timeout=10):\n    \"\"\"Make a GET request with proper error handling.\"\"\"\n    try:\n        response = requests.get(url, params=params, timeout=timeout)\n        response.raise_for_status()  # Raises HTTPError for 4xx/5xx\n        return response.json()\n    except requests.exceptions.Timeout:\n        print(f\"Timeout fetching {url}\")\n    except requests.exceptions.HTTPError as e:\n        print(f\"HTTP error: {e.response.status_code} - {e.response.reason}\")\n    except requests.exceptions.ConnectionError:\n        print(f\"Connection failed for {url}\")\n    except requests.exceptions.JSONDecodeError:\n        print(f\"Invalid JSON response from {url}\")\n    return None\n\n# Test with valid URL\ndata = safe_get('https://jsonplaceholder.typicode.com/posts/1')\nif data:\n    print(f\"Title: {data['title']}\")\n\n# Test with invalid URL\ndata = safe_get('https://jsonplaceholder.typicode.com/invalid')", "outputs": [], "execution_count": None},
                {"cell_type": "markdown", "metadata": {}, "source": "## 4. POST Request"},
                {"cell_type": "code", "metadata": {}, "source": "# Create a new resource (simulated by JSONPlaceholder)\nnew_post = {\n    'title': 'My API Post',\n    'body': 'This is created via the API',\n    'userId': 1\n}\n\nresponse = requests.post(\n    'https://jsonplaceholder.typicode.com/posts',\n    json=new_post,  # auto-sets Content-Type: application/json\n    headers={'Accept': 'application/json'}\n)\n\nprint(f\"Status: {response.status_code}\")\nprint(f\"Created: {json.dumps(response.json(), indent=2)}\")", "outputs": [], "execution_count": None},
                {"cell_type": "markdown", "metadata": {}, "source": "## Next Steps\n\n- Try fetching data from other public APIs (GitHub, weather, etc.)\n- Add authentication headers for protected APIs\n- Build a data pipeline: fetch -> transform -> analyze"},
            ],
        },
    },
    {
        "name": "Machine Learning Starter",
        "description": "Build your first ML model with scikit-learn: data prep, train/test split, model training, evaluation, and prediction.",
        "category": "Machine Learning",
        "difficulty_level": "intermediate",
        "estimated_minutes": 50,
        "tags": ["scikit-learn", "machine-learning", "classification"],
        "is_public": True,
        "sort_order": 5,
        "notebook": {
            "nbformat": 4,
            "nbformat_minor": 5,
            "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
            "cells": [
                {"cell_type": "markdown", "metadata": {}, "source": "# Machine Learning Starter\n\nBuild your first ML model using scikit-learn.\n\n**Topics covered:**\n- Loading and exploring data\n- Train/test split\n- Training a classifier\n- Model evaluation\n- Making predictions"},
                {"cell_type": "code", "metadata": {}, "source": "import numpy as np\nimport pandas as pd\nimport matplotlib.pyplot as plt\nimport seaborn as sns\nfrom sklearn.datasets import load_iris\nfrom sklearn.model_selection import train_test_split\nfrom sklearn.preprocessing import StandardScaler\nfrom sklearn.ensemble import RandomForestClassifier\nfrom sklearn.metrics import classification_report, confusion_matrix, accuracy_score\n\nsns.set_theme(style='whitegrid')\nprint(\"Libraries loaded!\")", "outputs": [], "execution_count": None},
                {"cell_type": "markdown", "metadata": {}, "source": "## 1. Load and Explore Data"},
                {"cell_type": "code", "metadata": {}, "source": "# Load the Iris dataset\niris = load_iris()\ndf = pd.DataFrame(iris.data, columns=iris.feature_names)\ndf['species'] = pd.Categorical.from_codes(iris.target, iris.target_names)\n\nprint(f\"Dataset shape: {df.shape}\")\nprint(f\"Classes: {list(iris.target_names)}\")\nprint(f\"\\nSamples per class:\")\nprint(df['species'].value_counts())\nprint(f\"\\nFirst 5 rows:\")\ndf.head()"},
                {"cell_type": "code", "metadata": {}, "source": "# Visualize feature distributions\nfig, axes = plt.subplots(2, 2, figsize=(12, 8))\nfor i, col in enumerate(iris.feature_names):\n    ax = axes[i // 2][i % 2]\n    for species in iris.target_names:\n        subset = df[df['species'] == species]\n        ax.hist(subset[col], alpha=0.6, label=species, bins=15)\n    ax.set_title(col)\n    ax.legend()\nplt.suptitle('Feature Distributions by Species', fontsize=14, fontweight='bold')\nplt.tight_layout()\nplt.show()", "outputs": [], "execution_count": None},
                {"cell_type": "markdown", "metadata": {}, "source": "## 2. Prepare Data"},
                {"cell_type": "code", "metadata": {}, "source": "# Split features and target\nX = df[iris.feature_names].values\ny = iris.target\n\n# Train/test split (80/20)\nX_train, X_test, y_train, y_test = train_test_split(\n    X, y, test_size=0.2, random_state=42, stratify=y\n)\n\n# Scale features\nscaler = StandardScaler()\nX_train_scaled = scaler.fit_transform(X_train)\nX_test_scaled = scaler.transform(X_test)\n\nprint(f\"Training set: {X_train.shape[0]} samples\")\nprint(f\"Test set: {X_test.shape[0]} samples\")", "outputs": [], "execution_count": None},
                {"cell_type": "markdown", "metadata": {}, "source": "## 3. Train Model"},
                {"cell_type": "code", "metadata": {}, "source": "# Train a Random Forest classifier\nmodel = RandomForestClassifier(\n    n_estimators=100,\n    max_depth=3,\n    random_state=42\n)\n\nmodel.fit(X_train_scaled, y_train)\n\n# Feature importance\nimportance = pd.Series(\n    model.feature_importances_,\n    index=iris.feature_names\n).sort_values(ascending=False)\n\nprint(\"Feature Importance:\")\nfor feat, imp in importance.items():\n    print(f\"  {feat}: {imp:.3f}\")", "outputs": [], "execution_count": None},
                {"cell_type": "markdown", "metadata": {}, "source": "## 4. Evaluate Model"},
                {"cell_type": "code", "metadata": {}, "source": "# Predict on test set\ny_pred = model.predict(X_test_scaled)\n\nprint(f\"Accuracy: {accuracy_score(y_test, y_pred):.2%}\")\nprint(f\"\\nClassification Report:\")\nprint(classification_report(y_test, y_pred, target_names=iris.target_names))\n\n# Confusion matrix\nfig, ax = plt.subplots(figsize=(7, 5))\ncm = confusion_matrix(y_test, y_pred)\nsns.heatmap(cm, annot=True, fmt='d', cmap='Blues',\n            xticklabels=iris.target_names,\n            yticklabels=iris.target_names, ax=ax)\nax.set_xlabel('Predicted')\nax.set_ylabel('Actual')\nax.set_title('Confusion Matrix', fontsize=14, fontweight='bold')\nplt.tight_layout()\nplt.show()", "outputs": [], "execution_count": None},
                {"cell_type": "markdown", "metadata": {}, "source": "## Next Steps\n\n- Try different classifiers: `SVC`, `KNeighborsClassifier`, `GradientBoostingClassifier`\n- Use `GridSearchCV` for hyperparameter tuning\n- Load your own dataset with `pd.read_csv()`"},
            ],
        },
    },
    {
        "name": "Blank Notebook",
        "description": "Start with a clean slate. An empty notebook ready for your code.",
        "category": "Getting Started",
        "difficulty_level": "beginner",
        "estimated_minutes": None,
        "tags": ["blank", "empty", "starter"],
        "is_public": True,
        "sort_order": 0,
        "notebook": {
            "nbformat": 4,
            "nbformat_minor": 5,
            "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"}},
            "cells": [
                {"cell_type": "code", "metadata": {}, "source": "# Start coding here\n", "outputs": [], "execution_count": None},
            ],
        },
    },
]


def main():
    # Connect to DB
    conn = mysql.connector.connect(**DB_CONFIG)
    cursor = conn.cursor()

    # Connect to S3 (MinIO)
    s3 = boto3.client("s3", **S3_CONFIG, region_name="us-east-1")

    inserted = 0
    for tmpl in TEMPLATES:
        template_id = str(uuid.uuid4())
        storage_path = f"templates/{template_id}/notebook.ipynb"
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")

        # Insert into DB
        cursor.execute(
            """INSERT INTO notebook_templates
            (id, name, description, category, storage_path, difficulty_level,
             estimated_minutes, tags, is_public, created_by, sort_order, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (
                template_id,
                tmpl["name"],
                tmpl["description"],
                tmpl["category"],
                storage_path,
                tmpl["difficulty_level"],
                tmpl["estimated_minutes"],
                json.dumps(tmpl["tags"]),
                tmpl["is_public"],
                ADMIN_USER_ID,
                tmpl["sort_order"],
                now,
                now,
            ),
        )

        # Upload notebook to S3
        notebook_json = json.dumps(tmpl["notebook"], indent=2)
        s3.put_object(
            Bucket=S3_BUCKET,
            Key=storage_path,
            Body=notebook_json.encode("utf-8"),
            ContentType="application/json",
        )

        inserted += 1
        print(f"  [+] {tmpl['name']} ({template_id[:8]}...)")

    conn.commit()
    cursor.close()
    conn.close()

    print(f"\nDone! Inserted {inserted} templates into DB + S3.")


if __name__ == "__main__":
    main()
