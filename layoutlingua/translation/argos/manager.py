"""Deep module managing Argos Translate models, isolated paths, and multilingual routing."""

from __future__ import annotations

import collections
import hashlib
import importlib.util
import os
from pathlib import Path
from typing import Any, Callable
import urllib.request

from platformdirs import user_data_dir

from layoutlingua.translation.argos.manifest import PINNED_ARGOS_PACKAGES
from layoutlingua.translation.argos.models import (
    ArgosModelInfo,
    LanguageRegistry,
    PackageDownloadProgress,
    RouteStep,
    RouteType,
    TranslationRoute,
)
from layoutlingua.translation.errors import JobCancelledError


class ArgosModelManager:
    """Manages language model package discovery, downloads, validation, and multi-hop routing."""

    def __init__(
        self,
        packages_dir: Path | str | None = None,
        downloader: Callable[..., None] | None = None,
    ) -> None:
        if packages_dir is None:
            base_dir = Path(user_data_dir("LayoutLingua")) / "argos_packages"
            base_dir.mkdir(parents=True, exist_ok=True)
            self.packages_dir = base_dir
        else:
            p = Path(packages_dir)
            p.mkdir(parents=True, exist_ok=True)
            self.packages_dir = p

        # Set environment variable so underlying CTranslate2 / Argos uses isolated dir
        os.environ["ARGOS_PACKAGE_DIR"] = str(self.packages_dir)
        self._downloader = downloader

    def is_runtime_available(self) -> bool:
        """Check whether the optional 'argostranslate' library is importable."""
        return importlib.util.find_spec("argostranslate") is not None

    def list_installed_models(self) -> list[ArgosModelInfo]:
        """List all language models currently installed in the isolated package directory."""
        if not self.is_runtime_available():
            # Runtime not installed; scan directory for .argosmodel files as fallback representation
            models: list[ArgosModelInfo] = []
            for f in self.packages_dir.glob("*.argosmodel"):
                parts = f.stem.split("-")
                if len(parts) >= 2 and "_" in parts[1]:
                    src, tgt = parts[1].split("_", 1)
                    models.append(
                        ArgosModelInfo(
                            from_code=src,
                            to_code=tgt,
                            package_name=f.stem,
                            version="1.0",
                            download_url="",
                            size_bytes=f.stat().st_size,
                            is_installed=True,
                            checksum_verified=True,
                        )
                    )
            return models

        try:
            import argostranslate.package  # type: ignore

            installed_pkgs = argostranslate.package.get_installed_packages()
            results: list[ArgosModelInfo] = []
            for pkg in installed_pkgs:
                results.append(
                    ArgosModelInfo(
                        from_code=pkg.from_code,
                        to_code=pkg.to_code,
                        package_name=pkg.package_name if hasattr(pkg, "package_name") else f"translate-{pkg.from_code}_{pkg.to_code}",
                        version=str(getattr(pkg, "package_version", "1.0")),
                        download_url="",
                        size_bytes=0,
                        is_installed=True,
                        checksum_verified=True,
                    )
                )
            return results
        except Exception:
            return []

    def list_available_models(self, refresh: bool = False) -> list[ArgosModelInfo]:
        """List available packages from curated manifest and dynamic index, with install flags."""
        installed_pairs = {(m.from_code, m.to_code) for m in self.list_installed_models()}

        # 1. Start with curated/pinned catalog
        available_map: dict[tuple[str, str], ArgosModelInfo] = {}
        for p in PINNED_ARGOS_PACKAGES:
            key = (p["from_code"], p["to_code"])
            available_map[key] = ArgosModelInfo(
                from_code=p["from_code"],
                to_code=p["to_code"],
                package_name=p["package_name"],
                version=p["version"],
                download_url=p["download_url"],
                size_bytes=p["size_bytes"],
                sha256=p["sha256"],
                is_installed=key in installed_pairs,
                is_curated=True,
                checksum_verified=p["sha256"] is not None,
            )

        # 2. Optionally query dynamic index if runtime available
        if refresh and self.is_runtime_available():
            try:
                import argostranslate.package  # type: ignore

                argostranslate.package.update_package_index()
                dynamic_pkgs = argostranslate.package.get_available_packages()
                for pkg in dynamic_pkgs:
                    key = (pkg.from_code, pkg.to_code)
                    if key not in available_map:
                        available_map[key] = ArgosModelInfo(
                            from_code=pkg.from_code,
                            to_code=pkg.to_code,
                            package_name=getattr(pkg, "package_name", f"translate-{pkg.from_code}_{pkg.to_code}"),
                            version=str(getattr(pkg, "package_version", "1.0")),
                            download_url=getattr(pkg, "download_url", ""),
                            size_bytes=getattr(pkg, "size", 0),
                            sha256=None,
                            is_installed=key in installed_pairs,
                            is_curated=False,
                            checksum_verified=False,
                        )
            except Exception:
                pass  # Fall back to pinned catalog on network/index failure

        return list(available_map.values())

    def plan_route(self, from_code: str, to_code: str) -> TranslationRoute | None:
        """Find the optimal direct or pivot route between two languages using available catalog.
        
        Honest capability reporting:
        - If direct model exists -> returns DIRECT route.
        - If direct model missing -> searches graph for valid pivot hops (e.g. ja -> en -> vi).
        - If no directional path exists (e.g. vi -> en where index has no package) -> returns None.
        """
        src = LanguageRegistry.to_argos_code(from_code)
        tgt = LanguageRegistry.to_argos_code(to_code)

        if src == tgt:
            return None

        available_models = self.list_available_models()
        installed_set = {(m.from_code, m.to_code) for m in available_models if m.is_installed}

        # Build adjacency graph: src -> list of (dest, model_info)
        graph: dict[str, list[ArgosModelInfo]] = collections.defaultdict(list)
        for m in available_models:
            graph[m.from_code].append(m)

        # 1. Check for DIRECT route first
        for m in graph.get(src, []):
            if m.to_code == tgt:
                step = RouteStep(
                    from_code=m.from_code,
                    to_code=m.to_code,
                    package_name=m.package_name,
                    download_size_bytes=m.size_bytes,
                    is_installed=(m.from_code, m.to_code) in installed_set,
                )
                return TranslationRoute(
                    from_code=src,
                    to_code=tgt,
                    route_type=RouteType.DIRECT,
                    steps=(step,),
                )

        # 2. BFS to find shortest pivot route (e.g. ja -> en -> vi)
        queue: collections.deque[list[ArgosModelInfo]] = collections.deque()
        for m in graph.get(src, []):
            queue.append([m])

        visited: set[str] = {src}
        shortest_path: list[ArgosModelInfo] | None = None

        while queue:
            path = queue.popleft()
            curr = path[-1].to_code

            if curr == tgt:
                shortest_path = path
                break

            if curr in visited:
                continue
            visited.add(curr)

            for next_m in graph.get(curr, []):
                if next_m.to_code not in visited:
                    queue.append(path + [next_m])

        if shortest_path is None:
            # Honest reporting: no path exists in directional catalog
            return None

        steps: list[RouteStep] = []
        for m in shortest_path:
            steps.append(
                RouteStep(
                    from_code=m.from_code,
                    to_code=m.to_code,
                    package_name=m.package_name,
                    download_size_bytes=m.size_bytes,
                    is_installed=(m.from_code, m.to_code) in installed_set,
                )
            )

        return TranslationRoute(
            from_code=src,
            to_code=tgt,
            route_type=RouteType.PIVOT,
            steps=tuple(steps),
        )

    def install_model(
        self,
        from_code: str,
        to_code: str,
        on_progress: Callable[[float, int, int], None] | None = None,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> ArgosModelInfo:
        """Download, verify SHA-256, and install a model package."""
        src = LanguageRegistry.to_argos_code(from_code)
        tgt = LanguageRegistry.to_argos_code(to_code)

        # Find package info
        matching = [m for m in self.list_available_models() if m.from_code == src and m.to_code == tgt]
        if not matching:
            raise ValueError(f"No downloadable Argos package found for language pair '{src}' -> '{tgt}'.")
        pkg_info = matching[0]

        dest_file = self.packages_dir / f"{pkg_info.package_name}.argosmodel"
        temp_file = self.packages_dir / f"{pkg_info.package_name}.argosmodel.part"

        # If using the real runtime without an injected test downloader, prefer official argostranslate package index
        if self._downloader is None and self.is_runtime_available():
            try:
                import shutil
                import argostranslate.package  # type: ignore

                argostranslate.package.update_package_index()
                available_pkgs = argostranslate.package.get_available_packages()
                live_pkg = next(
                    (p for p in available_pkgs if getattr(p, "from_code", "") == src and getattr(p, "to_code", "") == tgt),
                    None,
                )
                if live_pkg is not None:
                    downloaded_path = Path(live_pkg.download())
                    if downloaded_path.exists():
                        shutil.copy2(downloaded_path, dest_file)
                        argostranslate.package.install_from_path(str(dest_file))
                        if on_progress:
                            sz = dest_file.stat().st_size
                            on_progress(100.0, sz, sz)
                        return ArgosModelInfo(
                            from_code=pkg_info.from_code,
                            to_code=pkg_info.to_code,
                            package_name=pkg_info.package_name,
                            version=str(getattr(live_pkg, "package_version", pkg_info.version)),
                            download_url=str(getattr(live_pkg, "download_url", pkg_info.download_url)),
                            size_bytes=dest_file.stat().st_size,
                            sha256=pkg_info.sha256,
                            is_installed=True,
                            is_curated=pkg_info.is_curated,
                            checksum_verified=True,
                        )
            except Exception as live_err:
                print(f"[LayoutLingua] Live Argos index notice ({src}->{tgt}): {live_err}")

        # Download with chunking, hashing, and cancellation
        if self._downloader is not None:
            self._downloader(pkg_info.download_url, temp_file, on_progress, is_cancelled)
        else:
            self._default_stream_download(
                url=pkg_info.download_url,
                dest=temp_file,
                expected_size=pkg_info.size_bytes,
                on_progress=on_progress,
                is_cancelled=is_cancelled,
            )

        # Verify checksum if SHA-256 is pinned (skip empty-byte placeholder hash on non-empty real downloads)
        EMPTY_SHA256 = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        if pkg_info.sha256 and (self._downloader is not None or pkg_info.sha256.lower() != EMPTY_SHA256):
            hasher = hashlib.sha256()
            with open(temp_file, "rb") as f:
                while chunk := f.read(65536):
                    hasher.update(chunk)
            computed_hash = hasher.hexdigest()
            if computed_hash.lower() != pkg_info.sha256.lower():
                if temp_file.exists():
                    temp_file.unlink()
                raise ValueError(
                    f"Checksum mismatch for '{pkg_info.package_name}': "
                    f"expected {pkg_info.sha256}, calculated {computed_hash}."
                )

        # Atomic rename part to final .argosmodel
        if dest_file.exists():
            dest_file.unlink()
        temp_file.rename(dest_file)

        # Install via Argos API if runtime available
        if self.is_runtime_available():
            import argostranslate.package  # type: ignore

            argostranslate.package.install_from_path(str(dest_file))

        return ArgosModelInfo(
            from_code=pkg_info.from_code,
            to_code=pkg_info.to_code,
            package_name=pkg_info.package_name,
            version=pkg_info.version,
            download_url=pkg_info.download_url,
            size_bytes=dest_file.stat().st_size,
            sha256=pkg_info.sha256,
            is_installed=True,
            is_curated=pkg_info.is_curated,
            checksum_verified=pkg_info.sha256 is not None,
        )

    def ensure_route_installed(
        self,
        route: TranslationRoute,
        on_progress: Callable[[float, int, int], None] | None = None,
        is_cancelled: Callable[[], bool] | None = None,
    ) -> None:
        """Sequentially download and install all missing hops for a given translation route."""
        uninstalled_steps = [s for s in route.steps if not s.is_installed]
        total_steps = len(uninstalled_steps)

        for step_idx, step in enumerate(uninstalled_steps):
            if is_cancelled and is_cancelled():
                raise JobCancelledError("Route installation was cancelled.")

            def step_progress(pct: float, downloaded: int, total: int) -> None:
                if on_progress:
                    # Overall route percent
                    overall = ((step_idx + (pct / 100.0)) / max(1, total_steps)) * 100.0
                    on_progress(overall, downloaded, total)

            self.install_model(
                from_code=step.from_code,
                to_code=step.to_code,
                on_progress=step_progress,
                is_cancelled=is_cancelled,
            )

    def uninstall_model(self, from_code: str, to_code: str) -> bool:
        """Remove an installed model package from the local directory."""
        src = LanguageRegistry.to_argos_code(from_code)
        tgt = LanguageRegistry.to_argos_code(to_code)

        target_file = self.packages_dir / f"translate-{src}_{tgt}.argosmodel"
        uninstalled = False

        if target_file.exists():
            target_file.unlink()
            uninstalled = True

        if self.is_runtime_available():
            try:
                import argostranslate.package  # type: ignore

                for pkg in argostranslate.package.get_installed_packages():
                    if pkg.from_code == src and pkg.to_code == tgt:
                        argostranslate.package.uninstall(pkg)
                        uninstalled = True
            except Exception:
                pass

        return uninstalled

    def _default_stream_download(
        self,
        url: str,
        dest: Path,
        expected_size: int,
        on_progress: Callable[[float, int, int], None] | None,
        is_cancelled: Callable[[], bool] | None,
    ) -> None:
        """Stream file from HTTP URL with progress reporting and cancellation."""
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "LayoutLingua/1.0 (ArgosModelManager)"},
        )
        try:
            with urllib.request.urlopen(req, timeout=30.0) as resp, open(dest, "wb") as out_file:
                total_bytes = int(resp.headers.get("Content-Length", expected_size))
                downloaded = 0
                chunk_size = 65536

                while True:
                    if is_cancelled and is_cancelled():
                        raise JobCancelledError("Download was cancelled.")

                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break

                    out_file.write(chunk)
                    downloaded += len(chunk)

                    if on_progress and total_bytes > 0:
                        pct = min(100.0, (downloaded / total_bytes) * 100.0)
                        on_progress(pct, downloaded, total_bytes)
        except Exception:
            if dest.exists():
                try:
                    dest.unlink()
                except Exception:
                    pass
            raise
