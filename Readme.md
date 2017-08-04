# idetect

Start LocalDB, Flask App, Jupyter:
```
docker-compose up
```

Rebuild after changing requirements.txt:
```
docker-compose build
```

Just start LocalDB (eg. for running unit tests in an IDE):
```
docker-compose up localdb
```

Run unit tests in docker:
```
docker-compose up unittests
```