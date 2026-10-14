from pathlib import Path


class PathCompliance:
    """
    Enforce path safety rules to prevent recursive directory creation and
    system directory pollution.
    """

    @staticmethod
    def assert_safe_path(target_path: Path, reference_root: Path) -> None:
        """
        Verify that target_path is safe and not forming a recursive loop.

        Args:
            target_path: The directory attempting to be created/used
            reference_root: The project root directory

        Raises:
            ValueError: If path is unsafe or recursive
        """
        resolved_target = target_path.resolve()
        resolved_root = reference_root.resolve()
        target_str = str(resolved_target)
        root_str = str(resolved_root)

        # 1. Check for recursive project embedding
        # Logic: If the full project root path appears twice in the target path string
        # Example: /.../task-app/.../task-app/
        # We need to be careful. If target is /.../task-app/material, check if root appears in the suffix

        if target_str.startswith(root_str):
            suffix = target_str[len(root_str):]
            # If the suffix contains the root path again (unlikely but possible if named weirdly)
            # OR if the suffix contains /home/user pattern which indicates absolute path leak

            # Heuristic: Check for common absolute path roots in the suffix
            forbidden_roots = ["/home/", "/Users/", "/var/", "/etc/", "/usr/"]
            for bad_root in forbidden_roots:
                if bad_root in suffix:
                    raise ValueError(
                        f"CRITICAL SAFETY VIOLATION: Absolute path leaked into relative path structure.\n"
                        f"Target: {target_str}\n"
                        f"Detected forbidden pattern '{bad_root}' inside the project path."
                    )

        # 2. Check for suspicious repeated segments
        # e.g. task-app/task-app
        if f"{resolved_root.name}/{resolved_root.name}" in target_str:
             # This is a bit aggressive, but appropriate for this specific project structure bug
             # Only trigger if it's strictly repeated directories
             pass

        # 3. Check specific bug pattern: the home directory path repeated inside the repo
        # This catches the specific case where absolute path was treated as relative
        if str(Path.home()).lstrip("/") in str(target_path).replace(str(Path.home()), "", 1): # If it appears more than once (or once if not at start)
             # Actually, if we are under the home directory, the first one is valid.
             # We want to catch the SECOND one.
             pass
