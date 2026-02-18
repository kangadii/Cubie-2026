import plotly.express as px
import pandas as pd
import os
import sys

print(f"Python executable: {sys.executable}")
print(f"Current working directory: {os.getcwd()}")

try:
    print("Creating dataframe...")
    df = pd.DataFrame({
        "x": [1, 2, 3],
        "y": [10, 20, 30]
    })
    
    print("Creating figure...")
    fig = px.bar(df, x="x", y="y", title="Test Chart")
    
    out_dir = "public/demo"
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "test_chart.png")
    
    print(f"Saving image to {path}...")
    # Try with kaleido engine explicitly
    fig.write_image(path, format="png", engine="kaleido")
    print("Success!")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
