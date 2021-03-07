DROP TABLE IF EXISTS results;
DROP TABLE IF EXISTS full_results;
DROP TABLE IF EXISTS users;

CREATE TABLE results (
  id TEXT PRIMARY KEY,
	sample_name TEXT NOT NULL,
	status TEXT DEFAULT "processing",
	project_id TEXT,
	result TEXT,
	created TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
	user_id TEXT,
	lineage TEXT,
	drtype TEXT
);

CREATE TABLE full_results (
  id TEXT PRIMARY KEY,
	sample_name TEXT,
	main_lineage TEXT,
	sub_lineage TEXT,
	DR_type TEXT,
	MDR TEXT,
	XDR TEXT,
	rifampicin TEXT,
	isoniazid TEXT,
	pyrazinamide TEXT,
	ethambutol TEXT,
	streptomycin TEXT,
	fluoroquinolones TEXT,
	moxifloxacin TEXT,
	ofloxacin TEXT,
	levofloxacin TEXT,
	ciprofloxacin TEXT,
	aminoglycosides TEXT,
	amikacin TEXT,
	kanamycin TEXT,
	capreomycin TEXT,
	ethionamide TEXT,
	para_aminosalicylic_acid TEXT,
	cycloserine TEXT,
	linezolid TEXT,
	bedaquiline TEXT,
	clofazimine TEXT,
	delamanid TEXT,
	FOREIGN KEY (id) REFERENCES results (id)
);

CREATE TABLE users (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  username TEXT UNIQUE NOT NULL,
	forename TEXT,
	surname TEXT,
	institution TEXT,
	country TEXT,
  password TEXT NOT NULL
);
