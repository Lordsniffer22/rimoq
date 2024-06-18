docker exec -it gosty rm fia.py
wget -O fia.py https://raw.githubusercontent.com/Lordsniffer22/rimoq/main/fia.py
wget -O keyboards.py https://raw.githubusercontent.com/Lordsniffer22/rimoq/main/keyboards.py
docker cp fia.py gosty:/app
docker cp keyboards.py gosty:/app
docker restart gosty
rm -rf fia.py keyboards.py
