-- Создание баз данных и пользователей для всех модулей

-- БД для МВАЛ
CREATE USER mval WITH PASSWORD 'mval_secret';
CREATE DATABASE mval OWNER mval;

-- БД для Аналитика
CREATE DATABASE interview OWNER postgres;
