# nanoplanet
nanoplanet - very simple planet engine
=======

About
-------
[Planet Venus](https://github.com/rubys/venus) was great, unfortunately it is not developed
anymore and running Python 2 is not the easiest task and not the best idea from security point
of view. It also had problem handling emojis.
Needed simple planet engine to keep [Planet Jogger](https://github.com/rozie/PlanetJogger)
running, so decided to roll my own.

Script is created using Python 3 and tried to make it both simple and secure (using bleach
for sanitization). It uses Jinja2 templates and YAML for configuration.

Assumptions and limitations
-------
1. If feed is unreachable, it is skipped from current itaration.
2. Cron is used fetch feeds.
3. Owner names and feed URL are provided in the config.
4. Blog title is fetched from feed data.
5. Jinja 2 is used to generate output HTML files.
6. No cache is used.
7. Description, not full body is used as article content for the planet.
8. Each run is independent.
9. Publication date is used as article idientifier for simplicity - in practice collisions are unlikely.
10. N newest articles are published on the planet.
11. Output files have the same names as template files, with .tmpl removed.

How to use
-------
1. Create/adjust config file.
2. Crate/adjust template files.
3. Create Python 3 virtual envrironment.
4. Install requirements from requirements.txt.
5. Run the main script.

You can see it live at [Planet Jogger](https://zakr.es/planetjogger/index.html).