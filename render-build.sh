#!/usr/bin/env bash
apt-get install -y ffmpeg
pip install -r requirements.txt
```

Then change build command in Render to:
```
./render-build.sh