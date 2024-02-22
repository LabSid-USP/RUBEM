import os
import tempfile

import pytest
from sphinx.application import Sphinx


class TestSphinxDocBuild:

    @pytest.mark.integration
    def test_build_html_docs(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            src_dir = os.path.abspath("./doc/source")
            build_dir = os.path.join(temp_dir, "build/html")
            doctree_dir = os.path.join(temp_dir, "build/doctrees")

            app = Sphinx(
                srcdir=src_dir,
                confdir=src_dir,
                outdir=build_dir,
                doctreedir=doctree_dir,
                buildername="html",
            )

            app.build(force_all=True)

            assert os.path.exists(os.path.join(build_dir, "_images"))
            assert os.path.exists(os.path.join(build_dir, "_modules"))
            assert os.path.exists(os.path.join(build_dir, "_sources"))
            assert os.path.exists(os.path.join(build_dir, "_static"))
            assert os.path.exists(os.path.join(build_dir, "api.html"))
            assert os.path.exists(os.path.join(build_dir, "changelog.html"))
            assert os.path.exists(os.path.join(build_dir, "code-of-conduct.html"))
            assert os.path.exists(os.path.join(build_dir, "datasets.html"))
            assert os.path.exists(os.path.join(build_dir, "faq.html"))
            assert os.path.exists(os.path.join(build_dir, "fileformats.html"))
            assert os.path.exists(os.path.join(build_dir, "generated"))
            assert os.path.exists(os.path.join(build_dir, "genindex.html"))
            assert os.path.exists(os.path.join(build_dir, "index.html"))
            assert os.path.exists(os.path.join(build_dir, "installation.html"))
            assert os.path.exists(os.path.join(build_dir, "license.html"))
            assert os.path.exists(os.path.join(build_dir, "objects.inv"))
            assert os.path.exists(os.path.join(build_dir, "overview.html"))
            assert os.path.exists(os.path.join(build_dir, "preprocessing.html"))
            assert os.path.exists(os.path.join(build_dir, "py-modindex.html"))
            assert os.path.exists(os.path.join(build_dir, "search.html"))
            assert os.path.exists(os.path.join(build_dir, "searchindex.js"))
            assert os.path.exists(os.path.join(build_dir, "support.html"))
            assert os.path.exists(os.path.join(build_dir, "team.html"))
            assert os.path.exists(os.path.join(build_dir, "tutorials.html"))
            assert os.path.exists(os.path.join(build_dir, "userguide.html"))
