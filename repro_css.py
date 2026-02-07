
header_bg = "#eee"
border_color = "#ccc"
text_color = "#000"
twin_a_bg = "blue"
twin_b_bg = "red"
total_bg = "gray"

try:
    html = f'''
        <style>
            .workout-table {{ width: 100%; border-collapse: collapse; margin-bottom: 8px; font-size: 0.85rem; table-layout: fixed; }}
            .workout-table th {{ background-color: {header_bg}; padding: 8px; text-align: center; border: 1px solid {border_color}; font-weight: 600; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: {text_color}; }}
        </style>
    '''
    print("SUCCESS")
    print(html)
except NameError as e:
    print(f"NameError: {e}")
except Exception as e:
    print(f"Error: {e}")
