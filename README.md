# Retail Sales Analytics

**Introduction**

Retail Sales Analytics is a local dashboard for exploring weekly store and department performance. It uses the bundled sales data and a local SQLite database, with a lightweight interface served by Python's standard library.

<br />

**Table of Contents**

1. Key Technologies and Skills
2. Installation
3. Usage
4. Features
5. Contributing
6. License
7. Contact

<br />

**Key Technologies and Skills**
- Python
- Scikit-Learn
- SQLite
- Numpy
- Pandas
- Plotly (notebook charts)
- Matplotlib (notebook charts)
- Seaborn (notebook charts)

<br />

**Installation**

The dashboard needs only Python 3 and has no package-install step. For a one-click start, double-click `run.bat`. To start it from PowerShell:

```powershell
python app.py
```

The optional `Retail_Sales_Forecast.ipynb` notebook uses the packages listed in `requirements.txt`. To restore its Python environment, double-click `setup_notebook.bat`; it creates `.venv` and installs those packages. This environment is intentionally not included in the project folder because it takes several hundred megabytes. Open the notebook with the `.venv` Python interpreter after setup.

<br />

**Usage**

Run the dashboard from the project folder:

1. Double-click `run.bat`, or run `python app.py` in PowerShell.
2. The dashboard opens at `http://127.0.0.1:8000`.
3. Press **Ctrl+C** in the console window to stop it.

The app generates a repeatable synthetic dataset covering 2013–2025 and stores it in `retail_forecast.sqlite3`. The `requirements.txt` dependencies are for the optional notebook and model-training work, not for running the dashboard.

Weekly sales values are generated directly in Indian rupees, with modest amounts per store and department. No USD conversion is applied. The first launch replaces any older imported dataset in the local dashboard database with this synthetic dataset.

<br />

**Features**

**Data Preprocessing:**

- **Data Understanding**: The dataset comprises store, sales, and features data, offering details on store attributes like name, department, date, type, size, weekly sales, and environmental factors such as holiday status, temperature, fuel price, multiple markdowns, CPI, and unemployment. The primary focus is on predicting weekly sales, serving as the target variable for our modeling endeavors. This initial exploration forms the basis for subsequent data preprocessing and model development.

- **Encoding and Data Type Conversion**: The process involves preparing categorical features for modeling by transforming them into numerical representations, considering their inherent nature and relationship with the target variable. Simultaneously, data types are converted to align with the modeling process requirements, ensuring seamless integration and compatibility. This step facilitates the effective utilization of categorical information in the subsequent stages of the project.

- **Handling Null Values**: Notably, the 'MarkDown' columns present a challenge with over 50% null values, while other columns exhibit minimal null values. To address this, we employ machine learning models to predict and impute the missing values, ensuring a more complete and robust dataset for subsequent analysis and modeling. This strategic approach allows us to mitigate the impact of missing data on the overall quality of our dataset.

- **Feature Improvement**: Emphasizing enhanced modeling effectiveness, we concentrate on refining the dataset. This involves creating new features to extract deeper insights and enhance overall dataset efficiency. Evaluation, conducted through `Seaborn's Heatmap`, reveals that aside from Size and Type with correlation values of 0.21 and 0.17 (absolute value) respectively, no other columns exhibit a strong correlation with weekly sales. This underscores the need for a strategic feature enhancement to bolster the predictive power of our model.


**Machine Learning Regression Model**:

- **Multiple Models**: Recognizing the challenge posed by over 50% null values in the 'MarkDown' columns, we adopt a comprehensive approach. Two separate machine learning models are trained to predict weekly sales – one leveraging the 'MarkDown' features and another excluding them. This dual-model methodology enables a thorough examination of the influence of 'MarkDown' columns on predictive accuracy, shedding light on the optimal approach for incorporating this information into the modeling process.

- **Algorithm Assessment**: In the realm of regression, our primary objective is to predict the continuous variable of weekly sales. Our journey begins by splitting the dataset into training and testing subsets. We systematically apply various algorithms, evaluating them based on training and testing accuracy using the R2 (R-squared) metric, which signifies the coefficient of determination. This process allows us to identify the most suitable base algorithm tailored to our specific data.

- **Algorithm Selection**: After a thorough evaluation, two contenders, the Extra Trees Regressor and Random Forest Regressor, demonstrate commendable testing accuracy. Upon checking for any overfitting issues in both training and testing, both models exhibit strong performance without overfitting concerns. I choose the Random Forest Regressor for its ability to strike a balance between interpretability and accuracy, ensuring robust performance on unseen data.

- **Model Accuracy and Metrics**: Upon optimizing parameters, model1 and model2 exhibit impressive accuracies of 97.4% and 97.7%, respectively. Opting for model1 (with MarkDowns) ensures robust predictions for unseen data. Additional evaluation includes key metrics like mean absolute error, mean squared error, root mean squared error, and the coefficient of determination (R-squared), offering a comprehensive assessment of the model's performance and reliability.

- **Model Persistence**: We conclude this phase by saving our well-trained model to a pickle file. This strategic move enables us to effortlessly load the model whenever needed, streamlining the process of making predictions on weekly sales in future applications.


**Exploratory Data Analysis Dashboard:**

**Data Overview**:
- View the record count, years, stores, and departments in the local dataset.

**Sales Overview**: 
- Rank stores and departments by weekly sales, with filters for week, store, and department.

**Store Comparison**: 
- Compare the highest and lowest store totals for a selected week.

**Feature Analysis**: 
- Review average weekly sales by store type, holiday status, and store size.

**Sales Forecast**: 
- Estimate weekly sales for a store and department using the average of their four most recent available weeks. The page labels this as a baseline estimate, not a trained machine-learning prediction.

**About**:
- Review the dashboard data coverage, storage method, original INR values, and forecast method.

<br />

**Contributing**

Contributions to this project are welcome! If you encounter any issues or have suggestions for improvements, please feel free to submit a pull request.

<br />

**License**

This project is licensed under the MIT License. Please review the LICENSE file for more details.

<br />

**Contact**

📧 Email: saajidhmohamed018@gmail.com 

🌐 LinkedIn: [linkedin.com/in/chief018](https://www.linkedin.com/in/chief018)

For any further questions or inquiries, feel free to reach out. We are happy to assist you with any queries.
