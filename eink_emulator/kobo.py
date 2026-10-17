"""Tolino update packages hosted on Kobo's firmware CDN.

Kobo's update service only answers "what follows version X" and publishes no
checksums, so the releases the Tolino builder handles are pinned here. One
package serves every Tolino model; the importer selects the model's kernel.
5.13 removed OpenSSH, which the builder needs for USB SSH, and releases from
5.15 ship a recovery filesystem instead of rootfs.img.
"""

from __future__ import annotations

from .ftvdb import Release

CDN = "https://ereaderfiles.kobo.com/firmwares/kobo12"
TOLINO_RELEASES = (
    Release(
        "5.12.232736", 232736, "2025-10", "",
        (f"{CDN}/Oct2025/tolino-qt6-update-5.12.232736/update.tar",),
        sha256="814664e649dfbfbdf85bcfa2bbcc726d0698f81b464c9f8adc1b292c5b2dac37",
    ),
)


def releases() -> list[Release]:
    """Return the pinned Tolino releases, oldest first."""
    return sorted(TOLINO_RELEASES, key=lambda release: release.code)
