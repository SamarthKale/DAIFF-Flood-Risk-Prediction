"""Google Earth Engine side of the pipeline (spec §6.5, D-01, D-10).

Pure helpers are unit-tested offline; functions that build `ee` objects take the `ee` module as
an argument and are exercised by `@pytest.mark.gee` tests once a project is authenticated.
"""
