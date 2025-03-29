deploy: clean
    hugo build --ignoreCache && rsync -avz --delete public/ deploy@bienensteff.de:/srv/http/deploy/bienensteff.de

clean:
    rm -rf public

update-db:
    ./scripts/dump-db-sql.py > assets/db/db.json
