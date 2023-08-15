# directorfile
A python module to read and manipulate Macromedia (Adobe) Director files. It is currently in an early development stage.
  
## Usage
This package currently has two main entry points: `load_projector` and `load_director_archive`, which load 
Macromedia Director _projector_ and _archive_ files.

### Projector
A _projector_ file is an executable file wrapping a special _archive_ of type _application_ (``APPL``), which basically
contains a list of files as its resources.

Here is an example code for extracting all Xtra files from a projector file:
```python
from directorfile import load_projector

projector = load_projector(open(filename, 'rb'))

for filename, xtra in projector.application.xtras.items():
    with open(filename) as f:
        f.write(xtra.data)
```


### Archive
An _archive_ file is a container for multiple resources used for by a Director player.
There are essentially two types of _archive_ files - _Director_ and _Shockwave_.
Currently only _Director_ archives are supported.  

Here is an example code for extracting the _fontmap.txt_ file embedded in an archive:
```python
from directorfile import load_director_archive

archive = load_director_archive(open(filename, 'rb'))

for resource in archive.resources.values():
    if resource.TAG == 'FXmp':
        with open('fontmap.txt') as f:
                f.write(resource.data)
```

## Reference
In the creation of the code I used some reverse engineering as well as some of the following knowledge bases:  
 - https://github.com/n0samu/director-files-extract/tree/master  
 - https://gist.github.com/amaendle/49f9c27dc8d175fddc2483e719f721cf  
 - https://nosamu.medium.com/a-tour-of-the-adobe-director-file-format-e375d1e063c0  
 - https://docs.google.com/document/d/1jDBXE4Wv1AEga-o1Wi8xtlNZY4K2fHxW2Xs8RgARrqk/  
 - https://wiki.scummvm.org/index.php/Director