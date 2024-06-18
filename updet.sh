docker exec -it gosty rm creds.py
wget -O creds.py https://raw.githubusercontent.com/Lordsniffer22/rimoq/main/creds.py
docker cp creds.py gosty:/app
docker restart gosty
