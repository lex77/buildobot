PRAGMA journal_mode = WAL;
BEGIN TRANSACTION;

-- States table
CREATE TABLE states (
    id         INTEGER NOT NULL UNIQUE,
    gh_user    TEXT,
    gh_project TEXT,
    gh_branch  TEXT,
    gh_commit  TEXT,
    log_from   TEXT,
    log_to     TEXT,
    PRIMARY KEY(id)
);


-- Builds history
CREATE TABLE builds (
    id         INTEGER NOT NULL UNIQUE,
    user_id    INTEGER NOT NULL,
    datetime   INTEGER,
    gh_user    TEXT,
    gh_project TEXT,
    gh_branch  TEXT,
    gh_commit  TEXT,
    result     INTEGER,
    PRIMARY KEY(id)
);


-- Logs
CREATE TABLE log (
    id INTEGER NOT NULL UNIQUE,
    user_id INTEGER NOT NULL,
    datetime INTEGER,
    first_name TEXT,
    message TEXT,
    PRIMARY KEY(id)
);

COMMIT;