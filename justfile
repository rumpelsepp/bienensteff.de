deploy:
    hugo && rsync -avz --delete public/ deploy@bienensteff.de:/srv/http/deploy/bienensteff.de

update-db:
    ./scripts/dump-db-sql.py > assets/db/db.json
