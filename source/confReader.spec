# -*- mode: python -*-

block_cipher = None


a = Analysis(['confReader.py', 'errTrackers.py', 'fileObj.py', 'genericHelpers.py', 'rawFileReader.py', 'RDCauto2.0.1.py', 'RDCGUI.py'],
             pathex=['E:\\RAMPS\\Processing Code\\Repositories\\RDC2.0.0\\source'],
             binaries=[],
             datas=[],
             hiddenimports=[],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          a.binaries,
          a.zipfiles,
          a.datas,
          name='confReader',
          debug=False,
          strip=False,
          upx=True,
          runtime_tmpdir=None,
          console=True )
