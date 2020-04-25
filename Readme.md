# idetect

## intial setup

Edit `idetect/docker.env` to add the appropriate environment variables

Exporting the UID is necessary before build so that the user that everything
runs as inside the docker container matches the user on the host machine.
Without this, there will be a bunch of permissions problems, like things
failing because they can't write to the `.jupyter` or `.newspaper_scraper`
directories. This could also be avoided by _not_ volume mounting the code
into the containers, which would be an option in production. Having to
re`build` the images every time during development would be a real drag,
though.

To start localdb container in detached mode:

```bash
docker-compose up -d localdb
```

We start the workers in order to get it to run the setup.py script.

```
export UID
docker-compose build --build-arg UID=${UID} # NOTE: propagating UID parameter
docker-compose up workers
```

Next run the update script to create the fact API tables. Assuming the
localdb docker container is running and you have psql installed on your
host machine (e.g. you can use [instructions from here to install](https://linuxize.com/post/how-to-install-postgresql-on-ubuntu-18-04/), you can run:

```
psql -U postgres -h localhost -p 5433 idetect < source/data/update.sql
```

## running after initial setup

Start LocalDB, Workers, Flask App, Jupyter:
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

## manipulating the workers that are running

```
docker exec -it idetect_workers_1 bash
supervisorctl status                          # see what's running
supervisorctl stop all                        # stop all workers
supervisorctl start classifier:classifier-00  # start a single classifier
supervisorctl start extractor:*               # start all extractors
```

Logs for the workers are available on the host machine in `idetect/logs/workers` or
inside the docker container at `/var/log/workers`

## find the token for the notebook server

```
docker logs idetect_notebooks_1
```


## checking idetect user with python
```bash
$ sudo apt-get install python-pip
$ sudo apt-get install python-psycopg2
$ sudo apt-get install libpq-dev
$ pip3 install psycopg2
$ python3
>>>import psycopg2
>>>psycopg2.connect("dbname=idetect user=idetect host=localhost password=democracy port=5432")
```

The following result indicates user is not created:
```
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
  File "/home/alexbu/.local/lib/python3.5/site-packages/psycopg2/__init__.py", line 127, in connect
    conn = _connect(dsn, connection_factory=connection_factory, **kwasync)
psycopg2.OperationalError: FATAL:  password authentication failed for user "idetect"
FATAL:  password authentication failed for user "idetect"
```

The following result indicates the user is created
```
<connection object at 0x7f712de258d0; dsn: 'host=localhost user=idetect password=xxx dbname=idetect port=5432', closed: 0>
```

## manually creating required databases
```bash
$ sudo -u postgres psql
postgres=# CREATE USER idetect WITH PASSWORD 'democracy';
postgres=# CREATE DATABASE idetect;
postgres=# GRANT ALL PRIVILEGES ON DATABASE idetect TO idetect;
postgres=# CREATE USER tester WITH PASSWORD 'tester';
postgres=# CREATE DATABASE idetect_test;
postgres=# GRANT ALL PRIVILEGES ON DATABASE idetect_test to tester;
postgres=# \q
```


