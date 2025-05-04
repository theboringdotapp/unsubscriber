#!/usr/bin/env python3
import sys
import re
import os

def update_readme_stats(readme_path, stats_content):
    """Replaces content between markers in a file with new stats.

    Args:
        readme_path (str): Path to the README file.
        stats_content (str): The new statistics block (multi-line string).

    Returns:
        bool: True if the file was changed, False otherwise.
    """
    start_marker = '<!-- START_GIT_TIME_STATS -->'
    end_marker = '<!-- END_GIT_TIME_STATS -->'
    changed = False

    try:
        with open(readme_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Ensure markers exist
        if start_marker not in content or end_marker not in content:
            print(f"Error: Markers {start_marker} or {end_marker} not found in {readme_path}", file=sys.stderr)
            sys.exit(1) # Exit with error

        # Create the replacement pattern, ensuring it captures the markers themselves
        # DOTALL allows . to match newline characters
        pattern = re.compile(f"({re.escape(start_marker)}\\s*).*?(\\s*{re.escape(end_marker)})", re.DOTALL)
        
        # Construct the replacement string, keeping markers and adding new content
        # Add newlines before and after stats_content for clarity
        replacement = f"\\1\n{stats_content}\n\\2"

        new_content, num_subs = pattern.subn(replacement, content)

        if num_subs > 0 and new_content != content:
            with open(readme_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f'{readme_path} updated.')
            changed = True
        else:
            print(f'{readme_path} is already up-to-date or markers invalid.')

    except FileNotFoundError:
        print(f"Error: File not found: {readme_path}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error updating README: {e}", file=sys.stderr)
        sys.exit(1)

    return changed

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python update_readme.py <path_to_readme>", file=sys.stderr)
        sys.exit(1)

    readme_file = sys.argv[1]
    stats = os.environ.get('STATS_CONTENT')

    if stats is None:
        print("Error: STATS_CONTENT environment variable not set.", file=sys.stderr)
        sys.exit(1)

    file_changed = update_readme_stats(readme_file, stats)

    # Output for GitHub Actions
    # Note: ::set-output is deprecated, use environment files
    # https://github.blog/changelog/2022-10-11-github-actions-deprecating-save-state-and-set-output-commands/
    output_path = os.environ.get('GITHUB_OUTPUT', '/dev/null') # Default to /dev/null if not in Actions env
    with open(output_path, "a") as f:
        f.write(f"changed={str(file_changed).lower()}\n")

    sys.exit(0) # Exit successfully regardless of change, failure handled above 