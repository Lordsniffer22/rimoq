docker exec -it gosty rm fia.py
wget -O fia.py https://raw.githubusercontent.com/Lordsniffer22/rimoq/main/creds.py
docker cp fia.py gosty:/app
docker restart gosty
rm -rf fia.py
