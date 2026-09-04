-- Run this file once in psql while connected as postgres.
-- It creates project roles and the project database.
-- It does not delete or replace existing objects.

\set ON_ERROR_STOP on


CREATE ROLE factory_reader
    NOLOGIN
    NOSUPERUSER
    INHERIT
    NOCREATEDB
    NOCREATEROLE
    NOREPLICATION;

CREATE ROLE factory_admin
    LOGIN
    NOSUPERUSER
    INHERIT
    NOCREATEDB
    NOCREATEROLE
    NOREPLICATION;

CREATE ROLE factory_user
    LOGIN
    NOSUPERUSER
    INHERIT
    NOCREATEDB
    NOCREATEROLE
    NOREPLICATION;

CREATE ROLE factory_agent
    LOGIN
    NOSUPERUSER
    INHERIT
    NOCREATEDB
    NOCREATEROLE
    NOREPLICATION;


GRANT factory_reader TO factory_user, factory_agent;

\password factory_admin
\password factory_user
\password factory_agent


CREATE DATABASE factory_copilot_db OWNER factory_admin;