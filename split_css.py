import os

def extract_css():
    input_file = r'd:\CodeProject\knowledge-platform\thamkhao\app.css'
    output_dir = r'd:\CodeProject\knowledge-platform\web\css'
    
    with open(input_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    def get_lines(start, end=None):
        if end is None:
            return ''.join(lines[start-1:])
        return ''.join(lines[start-1:end-1])

    files = {
        'main.css': get_lines(1, 350),           # Global, sidebar, main, topbar, pages
        'modules/chat.css': get_lines(350, 877),     # Chat page
        'modules/search.css': get_lines(877, 1056),   # Search page
        'modules/connectors.css': get_lines(1056, 1971) + '\n' + get_lines(2991),     # Connectors page + sync progress
        'modules/history.css': get_lines(1971, 2001), # History page
        'modules/admin.css': get_lines(2001, 2228),   # Users page
        'components/toasts.css': get_lines(2228, 2561), # Toast and modals (will put them here for simplicity or split later, they are usually grouped with components)
        'components/login.css': get_lines(2561, 2635),  # Login screen
        'modules/graph.css': get_lines(2635, 2769),   # Graph page
        'modules/basket.css': get_lines(2769, 2991),  # Basket
        # The other files like buttons.css, layout.css can be injected or cleared since they are implicitly defined in main.css or chat.css
    }

    # Ensure directories exist
    os.makedirs(os.path.join(output_dir, 'components'), exist_ok=True)
    os.makedirs(os.path.join(output_dir, 'modules'), exist_ok=True)

    for relative_path, content in files.items():
        out_path = os.path.join(output_dir, relative_path)
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(content)

if __name__ == '__main__':
    extract_css()
