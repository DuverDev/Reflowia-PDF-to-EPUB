"""Generate version_info.txt for PyInstaller --version-file."""
import os

VERSION = (1, 2, 3, 0)

info = f"""# UTF-8
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers={VERSION},
    prodvers={VERSION},
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
        StringTable(
          '040904B0',
          [
            StringStruct('CompanyName', 'DMDev Labs'),
            StringStruct('FileDescription', 'Reflowia PDF to EPUB - Conversor Universal de PDF a EPUB'),
            StringStruct('FileVersion', '{VERSION[0]}.{VERSION[1]}.{VERSION[2]}.{VERSION[3]}'),
            StringStruct('InternalName', 'Reflowia PDF to EPUB'),
            StringStruct('LegalCopyright', 'Copyright (C) 2026 DMDev Labs - GPL-3.0 License'),
            StringStruct('OriginalFilename', 'Reflowia PDF to EPUB.exe'),
            StringStruct('ProductName', 'Reflowia PDF to EPUB'),
            StringStruct('ProductVersion', '{VERSION[0]}.{VERSION[1]}.{VERSION[2]}'),
            StringStruct('LegalTrademarks', 'Reflowia PDF to EPUB by DMDev Labs'),
          ]
        )
      ]
    ),
    VarFileInfo([VarStruct('Translation', [0x0409, 1200])])
  ]
)
"""

if __name__ == "__main__":
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "version_info.txt")
    with open(out, "w", encoding="utf-8") as f:
        f.write(info)
    print(f"version_info.txt generado (v{VERSION[0]}.{VERSION[1]}.{VERSION[2]})")
