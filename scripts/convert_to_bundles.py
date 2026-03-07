import os
import re
import shutil

# Configuration
CONTENT_DIR = "content/posts"
STATIC_IMAGES_DIR = "static/images"

def find_markdown_files(directory):
    """Finds all markdown files except ones already inside page bundles (index.md)."""
    md_files = []
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(".md") and file != "index.md":
                md_files.append(os.path.join(root, file))
    return md_files

def update_markdown_and_move_images(md_filepath):
    post_name = os.path.splitext(os.path.basename(md_filepath))[0]
    post_dir = os.path.join(CONTENT_DIR, post_name)
    
    with open(md_filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Find all image links matching /images/...
    # Regex explicitly targets markdown image syntax and frontmatter image declarations
    frontmatter_image_pattern = r'image\s*=\s*["\'](/images/[^"\']+)["\']'
    markdown_image_pattern = r'!\[([^\]]*)\]\((/images/[^\)]+)\)'

    frontmatter_matches = re.findall(frontmatter_image_pattern, content)
    markdown_matches = re.findall(markdown_image_pattern, content)

    images_to_move = set(frontmatter_matches + [m[1] for m in markdown_matches])

    if not images_to_move:
        print(f"Skipping {md_filepath} (no /images/ found)")
        return False

    # Create the page bundle directory
    os.makedirs(post_dir, exist_ok=True)
    
    # Move the markdown file and rename to index.md
    new_md_filepath = os.path.join(post_dir, "index.md")
    
    for relative_image_path in images_to_move:
        # relative_image_path looks like "/images/blogspot/iamqq/2010_08_22_014919.jpg"
        # Map to physical static path, removing leading slash
        static_image_path = os.path.join("static", relative_image_path.lstrip("/"))
        
        image_filename = os.path.basename(relative_image_path)
        new_image_path = os.path.join(post_dir, image_filename)
        
        # Move image if it exists in the static dir
        if os.path.exists(static_image_path):
            shutil.copy2(static_image_path, new_image_path)
            print(f"  Copied {static_image_path} -> {new_image_path}")
            
            # Update content string replacing absolute path with local filename
            content = content.replace(relative_image_path, image_filename)
        else:
            print(f"  WARNING: Image not found {static_image_path}")
            
    # Write the updated content to index.md
    with open(new_md_filepath, "w", encoding="utf-8") as f:
        f.write(content)
        
    print(f"Converted {md_filepath} to bundle -> {new_md_filepath}")
    
    # Remove original md file
    os.remove(md_filepath)
    return True

def main():
    print(f"Starting conversion in {CONTENT_DIR}")
    md_files = find_markdown_files(CONTENT_DIR)
    
    converted_count = 0
    for md_file in md_files:
        if update_markdown_and_move_images(md_file):
            converted_count += 1
            
    print(f"\nSuccessfully converted {converted_count} posts to page bundles.")

if __name__ == "__main__":
    main()
