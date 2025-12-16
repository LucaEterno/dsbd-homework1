CREATE TABLE IF NOT EXISTS user_airports (
    user_email VARCHAR(255) NOT NULL,
    airport_code CHAR(4) NOT NULL,
    high_value INT NULL,
    low_value INT NULL,
    PRIMARY KEY (user_email, airport_code)
);

CREATE TABLE IF NOT EXISTS flights (
    airport_code CHAR(4) NOT NULL,
    direction ENUM('arrival','departure') NOT NULL,
    flight_icao CHAR(6) NOT NULL,
    callsign VARCHAR(10) NOT NULL,
    flight_time DATETIME NOT NULL,
    PRIMARY KEY (airport_code, direction, flight_icao, flight_time)
);