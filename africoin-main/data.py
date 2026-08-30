import tkinter as tk
from tkinter import ttk, messagebox
from sqlalchemy import create_engine, MetaData, Table, select
import pandas as pd

# --- CONFIGURATION ---
DB_PATH = 'instance/users.db'  # Change to your SQLite database path

# --- DATABASE SETUP ---
engine = create_engine(f'sqlite:///{DB_PATH}')
metadata = MetaData()
metadata.reflect(bind=engine)

# --- GUI SETUP ---
root = tk.Tk()
root.title("SQLite Viewer (SQLAlchemy)")

# Table selection
tk.Label(root, text="Select Table:").pack(pady=5)
table_var = tk.StringVar()
table_dropdown = ttk.Combobox(root, textvariable=table_var)
table_dropdown['values'] = list(metadata.tables.keys())
table_dropdown.pack(pady=5)

# Treeview for displaying table data
tree_frame = tk.Frame(root)
tree_frame.pack(expand=True, fill='both')
tree_scroll = tk.Scrollbar(tree_frame)
tree_scroll.pack(side=tk.RIGHT, fill=tk.Y)
tree = ttk.Treeview(tree_frame, yscrollcommand=tree_scroll.set)
tree.pack(expand=True, fill='both')
tree_scroll.config(command=tree.yview)

# --- FUNCTIONS ---
def load_table():
    table_name = table_var.get()
    if table_name not in metadata.tables:
        messagebox.showerror("Error", "Table not found!")
        return

    # Clear existing data
    tree.delete(*tree.get_children())
    tree["columns"] = ()
    
    # Reflect the table
    table = Table(table_name, metadata, autoload_with=engine)
    
    # Fetch data
    stmt = select(table)
    results = engine.connect().execute(stmt)
    
    # Set tree columns
    columns = table.columns.keys()
    tree["columns"] = columns
    tree["show"] = "headings"
    for col in columns:
        tree.heading(col, text=col)
        tree.column(col, width=100)
    
    # Insert rows
    for row in results:
        tree.insert("", tk.END, values=[row[col] for col in columns])


# Load button
load_btn = tk.Button(root, text="Load Table", command=load_table)
load_btn.pack(pady=10)

root.mainloop()
