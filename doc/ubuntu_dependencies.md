# Package depencencies list for debian-based distros

The following depencencies is required to build uwsgi with plugins and to install Forest python dependencies: 

```
libzmq3-dev
libssl-dev
libcrypto++-dev
build-essential
python-dev
libpcre3-dev
libmariadbclient-dev
python-pip
```

Python requirements are listed in `requirements.txt` file and can be installed via pip:

`pip install -r requirements.txt`