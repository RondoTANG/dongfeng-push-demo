import pandas as pd

file_path = '/Users/RondoT/Documents/护卫军相关/01_用户与账户体系/员工党委分布列表.xlsx'
df = pd.read_excel(file_path)

# Fill empty with '-'
df = df.fillna('-')

has_l2 = len(df[df['下属党委'] != '-'])
has_l3 = len(df[df['三级党委'] != '-'])
has_l4 = len(df[df['四级党委'] != '-'])

print(f"Total rows: {len(df)}")
print(f"Rows with 下属党委: {has_l2}")
print(f"Rows with 三级党委: {has_l3}")
print(f"Rows with 四级党委: {has_l4}")

print("\n--- Example of deepest branches ---")
deepest = df[df['四级党委'] != '-'].head(5)
if len(deepest) == 0:
    deepest = df[df['三级党委'] != '-'].head(5)
    
if len(deepest) > 0:
    print(deepest.to_string())
else:
    print("No L3 or L4 found in the data.")
