pi@photonvision:~/coprocessor$ pip install pyntcore
Command 'pip' not found, but can be installed with:
sudo apt install python3-pip
pi@photonvision:~/coprocessor$ cd ..
pi@photonvision:~$ python
Command 'python' not found, did you mean:
  command 'python3' from deb python3
  command 'python' from deb python-is-python3
pi@photonvision:~$ python3 -m pip install pyntcore
/usr/bin/python3: No module named pip
pi@photonvision:~$ python3 -m pip3
/usr/bin/python3: No module named pip3
pi@photonvision:~$ python3 --version
Python 3.12.3