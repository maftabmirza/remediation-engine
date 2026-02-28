import os
import shutil

# Paths
BASE_DIR = r"d:\remediation-engine-vscode"
STATIC_DIR = os.path.join(BASE_DIR, "static")
THEMES_DIR = os.path.join(STATIC_DIR, "css", "themes")

STYLE_CSS = os.path.join(STATIC_DIR, "style.css")
STYLE_BAK = os.path.join(STATIC_DIR, "style.css.bak")

LIGHT_THEME = os.path.join(THEMES_DIR, "light.css")
AFTAB_THEME = os.path.join(THEMES_DIR, "aftab.css")
JACKSON_THEME = os.path.join(THEMES_DIR, "jackson.css")
JACKSON_OVERRIDES = os.path.join(THEMES_DIR, "jackson_overrides.css")

CUT_OFF_LINE = 738

def main():
    print(f"Refactoring CSS from {STYLE_CSS}...")

    # Ensure backup exists
    if not os.path.exists(STYLE_BAK):
        print(f"Creating backup {STYLE_BAK}...")
        shutil.copy2(STYLE_CSS, STYLE_BAK)
    else:
        print(f"Backup found at {STYLE_BAK}")

    # Read full style.css content
    with open(STYLE_BAK, "r", encoding="utf-8") as f:
        full_content = f.readlines()

    # 1. Create Light Theme (Full Copy)
    print(f"Creating {LIGHT_THEME}...")
    with open(LIGHT_THEME, "w", encoding="utf-8") as f:
        f.writelines(full_content)

    # 2. Create Aftab Theme (Full Copy)
    print(f"Creating {AFTAB_THEME}...")
    with open(AFTAB_THEME, "w", encoding="utf-8") as f:
        f.writelines(full_content)

    # 3. Create Jackson Theme (Base + Overrides)
    print(f"Refactoring {JACKSON_THEME}...")
    
    # Rename current Jackson override file if it hasn't been renamed yet
    if os.path.exists(JACKSON_THEME) and not os.path.exists(JACKSON_OVERRIDES):
        print(f"Renaming current {JACKSON_THEME} to {JACKSON_OVERRIDES}...")
        os.rename(JACKSON_THEME, JACKSON_OVERRIDES)
    
    # Read overrides
    if os.path.exists(JACKSON_OVERRIDES):
        with open(JACKSON_OVERRIDES, "r", encoding="utf-8") as f:
            overrides = f.read()
    else:
        overrides = ""
        print("Warning: No Jackson overrides found!")

    # Write new Jackson theme (Base + Overrides)
    with open(JACKSON_THEME, "w", encoding="utf-8") as f:
        f.writelines(full_content)
        f.write("\n\n/* ========================================= */\n")
        f.write("/* JACKSON THEME OVERRIDES                   */\n")
        f.write("/* ========================================= */\n\n")
        f.write(overrides)

    # 4. Truncate style.css to Layout Only
    print(f"Truncating {STYLE_CSS} to line {CUT_OFF_LINE}...")
    layout_content = full_content[:CUT_OFF_LINE]
    
    # Ensure layout content ends cleanly
    if not layout_content[-1].strip().endswith("}"):
        layout_content.append("}\n")

    with open(STYLE_CSS, "w", encoding="utf-8") as f:
        f.writelines(layout_content)
        f.write("\n/* End of Base Layout Styles */\n")

    print("CSS Refactoring Complete!")

if __name__ == "__main__":
    main()
