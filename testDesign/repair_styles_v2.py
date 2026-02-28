
import os

file_path = 'd:/testDesign/styles.css'

# The clean CSS we want to append
clean_css_block = """
/* Audit Page & Runbooks Styles */

/* Tabs */
.rb-tabs {
    display: flex;
    gap: 24px;
    border-bottom: 1px solid #e2e8f0;
    margin-bottom: 24px;
}

.rb-tab {
    background: none;
    border: none;
    padding: 12px 4px;
    font-size: 14px;
    font-weight: 500;
    color: #64748b;
    cursor: pointer;
    display: flex;
    align-items: center;
    gap: 8px;
    border-bottom: 2px solid transparent;
    transition: all 0.2s;
}

.rb-tab:hover {
    color: #1e293b;
}

.rb-tab.active {
    color: #3b82f6;
    border-bottom-color: #3b82f6;
    font-weight: 600;
}

.rb-tab svg {
    width: 16px;
    height: 16px;
}

/* Tables */
.rb-table-container {
    background: white;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    overflow: hidden;
    box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05); /* Added slight shadow */
}

.rb-table {
    width: 100%;
    border-collapse: collapse;
}

.rb-table th {
    padding: 12px 24px;
    background: #f8fafc;
    text-align: left;
    font-size: 12px;
    font-weight: 600;
    color: #64748b;
    border-bottom: 1px solid #e2e8f0;
}

.rb-table td {
    padding: 16px 24px;
    border-bottom: 1px solid #f1f5f9;
    font-size: 14px;
    color: #0f172a;
    vertical-align: middle;
}

.rb-table tr:last-child td {
    border-bottom: none;
}
"""

# Text from the end of the VALID file, before any corruption.
# Based on file view:
# 5431:     font-size: 13px;
# 5432:     color: #0f172a;
# 5433:     width: 100%;
# 5434: }
known_valid_end = """    width: 100%;
}"""

try:
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check if the known valid end exists
    if known_valid_end in content:
        print("Found known valid ending.")
        # Split and take the first part + the valid ending
        parts = content.split(known_valid_end)
        # Reconstruct the valid content: pure content up to the end of the valid block
        valid_content = parts[0] + known_valid_end
        
        # Now append the new block
        final_content = valid_content + "\n" + clean_css_block
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(final_content)
        print("Successfully repaired styles.css")
        
    else:
        print("Could not find known valid ending. Check file content manually.")
        # Debug: print last 200 chars
        print("Last 200 chars of read content:")
        print(content[-200:])

except Exception as e:
    print(f"Error: {e}")
