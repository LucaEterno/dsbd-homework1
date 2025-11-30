CREATE TABLE IF NOT EXISTS user_airports (
     user_email VARCHAR(255) NOT NULL,
    airport_code CHAR(4) NOT NULL,
    PRIMARY KEY (user_email, airport_code)
);

CREATE TABLE IF NOT EXISTS flights (
    airport_code CHAR(4) NOT NULL,
    direction VARCHAR(255) NOT NULL,
    flight_icao CHAR(6) NOT NULL,
    callsign VARCHAR(10) NOT NULL,
    flight_time DATETIME NOT NULL,
    PRIMARY KEY (flight_icao)
);