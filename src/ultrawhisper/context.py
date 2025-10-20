#!/usr/bin/env python3
"""
Context detection for UltraWhisper - detects active application and window information.
"""

import os
import re
import json
import shutil
import subprocess
from typing import Dict, Any, Optional, List, Union
from pathlib import Path
from loguru import logger


class ContextDetectionError(Exception):
    """Exception raised when context detection fails."""

    pass


class ContextDetector:
    """Detects active application context for prompt customization."""

    def __init__(self, config: Any):
        """Initialize context detector with configuration."""
        self.config = config
        # Access Pydantic model attributes directly
        self.context_enabled = config.context_detection
        self.dependencies_checked = False
        self.available_methods = []

        # Check available detection methods
        self._check_dependencies()

    def _check_dependencies(self) -> Dict[str, bool]:
        """Check which context detection methods are available."""
        deps = {
            "xdotool": bool(shutil.which("xdotool")),
            "xprop": bool(shutil.which("xprop")),
            "xwininfo": bool(shutil.which("xwininfo")),
            "x11_display": bool(os.environ.get("DISPLAY")),
            "wayland": bool(os.environ.get("WAYLAND_DISPLAY")),
        }

        # Determine available methods
        self.available_methods = []

        if deps["xdotool"] and deps["x11_display"]:
            self.available_methods.append("xdotool")

        if deps["xprop"] and deps["x11_display"]:
            self.available_methods.append("xprop")

        if deps["x11_display"]:
            self.available_methods.append("env_fallback")

        self.dependencies_checked = True

        logger.debug(f"Context detection dependencies: {deps}")
        logger.debug(f"Available methods: {self.available_methods}")

        return deps

    def get_dependency_status(self) -> Dict[str, Any]:
        """Get status of context detection dependencies."""
        if not self.dependencies_checked:
            deps = self._check_dependencies()
        else:
            deps = {
                "xdotool": "xdotool" in self.available_methods,
                "xprop": "xprop" in self.available_methods,
                "x11_display": bool(os.environ.get("DISPLAY")),
                "wayland": bool(os.environ.get("WAYLAND_DISPLAY")),
            }

        return {
            "dependencies": deps,
            "available_methods": self.available_methods,
            "context_enabled": self.context_enabled,
            "can_detect": len(self.available_methods) > 0,
            "recommendations": self._get_install_recommendations(deps),
        }

    def _get_install_recommendations(self, deps: Dict[str, bool]) -> List[str]:
        """Get installation recommendations for missing dependencies."""
        recommendations = []

        if not deps.get("x11_display") and deps.get("wayland"):
            recommendations.append("Running on Wayland - context detection is limited")
        elif not deps.get("x11_display"):
            recommendations.append("No display detected - are you in a GUI session?")

        if deps.get("x11_display"):
            if not deps.get("xdotool"):
                recommendations.append("Install xdotool: sudo apt install xdotool")
            if not deps.get("xprop"):
                recommendations.append("Install x11-utils: sudo apt install x11-utils")

        return recommendations

    def get_active_context(self, log_context: bool = False) -> Dict[str, Any]:
        """
        Get the active application context.

        Args:
            log_context: Whether to log context detection details

        Returns:
            Dictionary with context information
        """
        if not self.context_enabled:
            context = {"app": "disabled", "title": "", "method": "disabled"}
            if log_context:
                logger.info("Context detection is disabled")
            return context

        if not self.available_methods:
            context = {"app": "unavailable", "title": "", "method": "none"}
            if log_context:
                logger.warning("No context detection methods available")
            return context

        # Try detection methods in order of preference
        for method in self.available_methods:
            try:
                if method == "xdotool":
                    context = self._detect_with_xdotool()
                elif method == "xprop":
                    context = self._detect_with_xprop()
                elif method == "env_fallback":
                    context = self._detect_with_env()
                else:
                    continue

                context["method"] = method

                if log_context:
                    logger.info(f"Context Detection ({method}):")
                    logger.info(f"  App Class: {context.get('app', 'unknown')}")
                    logger.info(f"  Window Title: {context.get('title', '')}")
                    logger.info(f"  Raw Class: {context.get('raw_class', '')}")

                return context

            except Exception as e:
                logger.debug(f"Context detection method {method} failed: {e}")
                continue

        # All methods failed
        context = {"app": "unknown", "title": "", "method": "failed"}
        if log_context:
            logger.warning("All context detection methods failed")
        return context

    def _detect_with_xdotool(self) -> Dict[str, Any]:
        """Detect context using xdotool (most reliable method)."""
        try:
            # Get focused window ID
            window_id = (
                subprocess.check_output(
                    ["xdotool", "getwindowfocus"], stderr=subprocess.DEVNULL, timeout=2
                )
                .decode()
                .strip()
            )

            # Get window title
            title = (
                subprocess.check_output(
                    ["xdotool", "getwindowname", window_id],
                    stderr=subprocess.DEVNULL,
                    timeout=2,
                )
                .decode()
                .strip()
            )

            # Get window class using xprop
            wm_class_output = (
                subprocess.check_output(
                    ["xprop", "-id", window_id, "WM_CLASS"],
                    stderr=subprocess.DEVNULL,
                    timeout=2,
                )
                .decode()
                .strip()
            )

            # Parse WM_CLASS: WM_CLASS(STRING) = "instance", "class"
            app_class = "unknown"
            if "WM_CLASS(STRING)" in wm_class_output:
                # Extract the first quoted string (instance name)
                match = re.search(r'"([^"]+)"', wm_class_output)
                if match:
                    app_class = match.group(1).lower()

            return {
                "app": app_class,
                "title": title,
                "window_id": window_id,
                "raw_class": wm_class_output,
            }

        except (
            subprocess.TimeoutExpired,
            subprocess.CalledProcessError,
            FileNotFoundError,
        ) as e:
            raise ContextDetectionError(f"xdotool detection failed: {e}")

    def _detect_with_xprop(self) -> Dict[str, Any]:
        """Detect context using xprop as fallback."""
        try:
            # Get the focused window
            focus_output = (
                subprocess.check_output(
                    ["xprop", "-root", "_NET_ACTIVE_WINDOW"],
                    stderr=subprocess.DEVNULL,
                    timeout=2,
                )
                .decode()
                .strip()
            )

            # Extract window ID
            window_id = focus_output.split()[-1]

            # Get window class
            wm_class_output = (
                subprocess.check_output(
                    ["xprop", "-id", window_id, "WM_CLASS"],
                    stderr=subprocess.DEVNULL,
                    timeout=2,
                )
                .decode()
                .strip()
            )

            # Get window title
            title_output = (
                subprocess.check_output(
                    ["xprop", "-id", window_id, "WM_NAME"],
                    stderr=subprocess.DEVNULL,
                    timeout=2,
                )
                .decode()
                .strip()
            )

            # Parse outputs
            app_class = "unknown"
            if "WM_CLASS(STRING)" in wm_class_output:
                match = re.search(r'"([^"]+)"', wm_class_output)
                if match:
                    app_class = match.group(1).lower()

            title = "unknown"
            if "WM_NAME(STRING)" in title_output:
                match = re.search(r'"([^"]+)"', title_output)
                if match:
                    title = match.group(1)

            return {
                "app": app_class,
                "title": title,
                "window_id": window_id,
                "raw_class": wm_class_output,
            }

        except (
            subprocess.TimeoutExpired,
            subprocess.CalledProcessError,
            FileNotFoundError,
        ) as e:
            raise ContextDetectionError(f"xprop detection failed: {e}")

    def _detect_with_env(self) -> Dict[str, Any]:
        """Fallback context detection using environment variables."""
        # Check common environment variables that might give us context
        context = {"app": "unknown", "title": ""}

        # Check if we're in a terminal
        term = os.environ.get("TERM", "")
        term_program = os.environ.get("TERM_PROGRAM", "")

        if term_program:
            context["app"] = term_program.lower()
            context["title"] = f"Terminal ({term_program})"
        elif term:
            context["app"] = "terminal"
            context["title"] = f"Terminal ({term})"

        # Check SSH connection
        if os.environ.get("SSH_CLIENT") or os.environ.get("SSH_TTY"):
            context["app"] = "ssh"
            context["title"] = "SSH Session"

        return context

    def match_context_patterns(
        self, context: Dict[str, Any], patterns: List[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """
        Match context against configured patterns.

        Args:
            context: Current context information
            patterns: List of pattern configurations

        Returns:
            Matched pattern configuration or None
        """
        title = context.get("title", "")
        app = context.get("app", "")

        for pattern_config in patterns:
            pattern = pattern_config.get("match", "")

            try:
                # Try to match against window title
                if re.search(pattern, title, re.IGNORECASE):
                    logger.debug(
                        f"Pattern matched: '{pattern}' against title '{title}'"
                    )
                    return pattern_config

                # Try to match against app name
                if re.search(pattern, app, re.IGNORECASE):
                    logger.debug(f"Pattern matched: '{pattern}' against app '{app}'")
                    return pattern_config

            except re.error as e:
                logger.warning(f"Invalid regex pattern '{pattern}': {e}")
                continue

        return None


def create_context_detector(config: Dict[str, Any]) -> ContextDetector:
    """Create a context detector instance."""
    return ContextDetector(config)


# CLI testing functionality
if __name__ == "__main__":
    import argparse
    import time

    def main():
        parser = argparse.ArgumentParser(
            description="Test UltraWhisper context detection"
        )
        parser.add_argument(
            "--watch", action="store_true", help="Watch context changes"
        )
        parser.add_argument("--verbose", action="store_true", help="Verbose output")

        args = parser.parse_args()

        # Create detector
        config = {"context_detection": True}
        detector = ContextDetector(config)

        # Check dependencies
        status = detector.get_dependency_status()
        print("Context Detection Status:")
        print(f"  Enabled: {status['context_enabled']}")
        print(f"  Can Detect: {status['can_detect']}")
        print(f"  Available Methods: {status['available_methods']}")

        for dep, available in status["dependencies"].items():
            print(f"  {dep}: {'✓' if available else '✗'}")

        if status["recommendations"]:
            print("\nRecommendations:")
            for rec in status["recommendations"]:
                print(f"  • {rec}")

        if not status["can_detect"]:
            print("\nContext detection is not available.")
            return

        if args.watch:
            print(f"\nWatching context changes (Ctrl+C to stop)...")
            last_context = None

            try:
                while True:
                    current_context = detector.get_active_context(
                        log_context=args.verbose
                    )

                    if current_context != last_context:
                        timestamp = time.strftime("%H:%M:%S")
                        app = current_context.get("app", "unknown")
                        title = current_context.get("title", "")
                        method = current_context.get("method", "")

                        print(f"[{timestamp}] {app} ({method})")
                        if title:
                            print(f'          "{title}"')

                        last_context = current_context.copy()

                    time.sleep(1)

            except KeyboardInterrupt:
                print("\nStopped watching.")
        else:
            # Single detection
            context = detector.get_active_context(log_context=True)
            print(f"\nCurrent Context:")
            print(json.dumps(context, indent=2))

    main()
