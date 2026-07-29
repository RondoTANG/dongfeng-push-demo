import pandas as pd

file_path = '/Users/RondoT/Documents/护卫军相关/01_用户与账户体系/员工党委分布列表.xlsx'
try:
    df = pd.read_excel(file_path)
    print("Columns:", df.columns.tolist())
    print(df.head(10).to_string())
except Exception as e:
    print("Error:", e)
