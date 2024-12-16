Factorio data codec
===================

The game [Factorio](https://www.factorio.com/) uses a custom binary file format to save certain game data, including the `mod-settings.dat` file. While these settings may be modified via the in-game UI, this isn't possible when running a dedicated server: the `mod-settings.dat` file must be pre-loaded with the correct values during world generation.

This repository contains a codec for Factorio game data (implemented in Python) that can convert the `mod-settings.dat` file to JSON and back, making it possible to adjust the settings without having to create and upload a local world or hex-edit the file.


Usage
-----

To decode the settings, run in Command Prompt or PowerShell:

```doscon
> python factorio_data.py c:\...\mods\mod-settings.dat
Reading DAT file 'c:\...\mods\mod-settings.dat'...
Writing JSON file 'c:\...\mods\mod-settings.json'...
```

Edit the `mod-settings.json` file in Notepad or any other text editor.

To re-encode the settings, run in Command Prompt or PowerShell:

```doscon
> python factorio_data.py c:\...\mods\mod-settings.json
Reading JSON file 'c:\...\mods\mod-settings.json'...
Writing DAT file 'c:\...\mods\mod-settings.dat'...
```

If no modifications were made, the resulting DAT file must be bit-for-bit identical to the original DAT file. (If it is not, please file an issue on this repository, and attach the problematic DAT file for investigation.)

On Windows, running the `python` command may cause Windows Store to open and prompt you to install Python. Do so. Otherwise, if you don't have Python installed, [download and install it first](https://www.python.org/downloads/).


Curiosity
---------

The `mod-settings.dat` file format is very similar to several other Factorio file formats, including the `level-init.dat` and `script.dat` files from saved games. However, these files contain additional data that isn't handled by this codec, and so it cannot decode them to JSON.


License
-------

[0-clause BSD](LICENSE-0BSD.txt).