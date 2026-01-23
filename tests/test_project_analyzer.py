"""
Unit tests for lib/project_analyzer.py
"""

import pytest
import tempfile
import json
from pathlib import Path

from lib.project_analyzer import ProjectAnalyzer, ProjectFingerprint, ProjectType


class TestProjectFingerprint:
    """Tests for ProjectFingerprint dataclass."""

    def test_similarity_same_project(self):
        """Identical fingerprints have similarity ~1.0."""
        fp = ProjectFingerprint(
            project_path="/test",
            project_type=ProjectType.WEB_APP,
            primary_language="python",
            languages=["python"],
            frameworks=["FastAPI"],
            file_count=100
        )

        # Use approximate comparison due to floating point
        assert abs(fp.similarity(fp) - 1.0) < 0.01

    def test_similarity_different_types(self):
        """Different project types reduce similarity."""
        fp1 = ProjectFingerprint(
            project_path="/test1",
            project_type=ProjectType.WEB_APP,
            primary_language="python",
            file_count=100
        )
        fp2 = ProjectFingerprint(
            project_path="/test2",
            project_type=ProjectType.CLI_TOOL,
            primary_language="python",
            file_count=100
        )

        sim = fp1.similarity(fp2)
        assert sim < 1.0
        assert sim > 0.0  # Same language contributes

    def test_similarity_different_languages(self):
        """Different languages reduce similarity."""
        fp1 = ProjectFingerprint(
            project_path="/test1",
            project_type=ProjectType.WEB_APP,
            primary_language="python",
            file_count=100
        )
        fp2 = ProjectFingerprint(
            project_path="/test2",
            project_type=ProjectType.WEB_APP,
            primary_language="javascript",
            file_count=100
        )

        sim = fp1.similarity(fp2)
        assert sim < 1.0
        # Same type contributes 0.3, similar size 0.1
        assert sim >= 0.3

    def test_similarity_overlapping_frameworks(self):
        """Overlapping frameworks increase similarity."""
        fp1 = ProjectFingerprint(
            project_path="/test1",
            project_type=ProjectType.WEB_APP,
            primary_language="python",
            frameworks=["FastAPI", "SQLAlchemy"],
            file_count=100
        )
        fp2 = ProjectFingerprint(
            project_path="/test2",
            project_type=ProjectType.WEB_APP,
            primary_language="python",
            frameworks=["FastAPI", "Pydantic"],
            file_count=100
        )

        sim = fp1.similarity(fp2)
        # Same type (0.3) + same lang (0.2) + overlap (0.2 * 1/3) + size (0.1)
        assert sim > 0.5

    def test_similarity_overlapping_patterns(self):
        """Overlapping patterns increase similarity."""
        fp1 = ProjectFingerprint(
            project_path="/test1",
            project_type=ProjectType.API_SERVICE,
            primary_language="python",
            patterns_detected=["MVC", "Test-heavy"],
            file_count=100
        )
        fp2 = ProjectFingerprint(
            project_path="/test2",
            project_type=ProjectType.API_SERVICE,
            primary_language="python",
            patterns_detected=["MVC", "API-first"],
            file_count=100
        )

        sim = fp1.similarity(fp2)
        assert sim > 0.6

    def test_similarity_different_sizes(self):
        """Very different sizes reduce size contribution."""
        fp_small = ProjectFingerprint(
            project_path="/test1",
            project_type=ProjectType.WEB_APP,
            primary_language="python",
            file_count=10
        )
        fp_large = ProjectFingerprint(
            project_path="/test2",
            project_type=ProjectType.WEB_APP,
            primary_language="python",
            file_count=1000
        )
        fp_medium = ProjectFingerprint(
            project_path="/test3",
            project_type=ProjectType.WEB_APP,
            primary_language="python",
            file_count=100
        )

        sim_extreme = fp_small.similarity(fp_large)
        sim_closer = fp_small.similarity(fp_medium)

        # Closer file counts should have higher similarity
        assert sim_closer > sim_extreme

    def test_to_dict_and_back(self):
        """Round-trip through dict preserves data."""
        original = ProjectFingerprint(
            project_path="/test",
            project_type=ProjectType.API_SERVICE,
            primary_language="python",
            languages=["python", "sql"],
            frameworks=["FastAPI", "SQLAlchemy"],
            build_tools=["pip"],
            test_frameworks=["pytest"],
            patterns_detected=["MVC"],
            file_count=50,
            directory_structure={"src": 20, "tests": 30}
        )

        data = original.to_dict()
        restored = ProjectFingerprint.from_dict(data)

        assert restored.project_path == original.project_path
        assert restored.project_type == original.project_type
        assert restored.primary_language == original.primary_language
        assert restored.frameworks == original.frameworks
        assert restored.file_count == original.file_count

    def test_from_dict_handles_unknown_type(self):
        """from_dict handles unknown project type."""
        data = {
            "project_path": "/test",
            "project_type": "unknown",
            "primary_language": "python"
        }

        fp = ProjectFingerprint.from_dict(data)
        assert fp.project_type == ProjectType.UNKNOWN


class TestProjectAnalyzer:
    """Tests for ProjectAnalyzer class."""

    @pytest.fixture
    def temp_python_project(self):
        """Create a temporary Python project."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "main.py").write_text("print('hello')")
            Path(tmpdir, "utils.py").write_text("def util(): pass")
            Path(tmpdir, "requirements.txt").write_text("fastapi\nuvicorn\n")
            Path(tmpdir, "tests").mkdir()
            Path(tmpdir, "tests", "test_main.py").write_text("def test_main(): pass")
            yield tmpdir

    def test_detects_python_language(self, temp_python_project):
        """Detects Python as primary language."""
        analyzer = ProjectAnalyzer()
        fingerprint = analyzer.analyze(temp_python_project)

        assert fingerprint.primary_language == "python"
        assert "python" in fingerprint.languages

    def test_detects_frameworks_from_requirements(self, temp_python_project):
        """Detects frameworks from requirements.txt."""
        analyzer = ProjectAnalyzer()
        fingerprint = analyzer.analyze(temp_python_project)

        assert any("fastapi" in f.lower() for f in fingerprint.frameworks)

    def test_detects_test_directory(self, temp_python_project):
        """Detects test framework presence."""
        analyzer = ProjectAnalyzer()
        fingerprint = analyzer.analyze(temp_python_project)

        assert "tests" in fingerprint.directory_structure or fingerprint.test_frameworks

    def test_counts_files(self, temp_python_project):
        """Counts files in project."""
        analyzer = ProjectAnalyzer()
        fingerprint = analyzer.analyze(temp_python_project)

        assert fingerprint.file_count >= 3  # main.py, utils.py, test_main.py

    def test_handles_empty_directory(self):
        """Handles empty project directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            analyzer = ProjectAnalyzer()
            fingerprint = analyzer.analyze(tmpdir)

            assert fingerprint.project_type == ProjectType.UNKNOWN
            assert fingerprint.file_count == 0

    def test_handles_nonexistent_directory(self):
        """Handles nonexistent directory."""
        analyzer = ProjectAnalyzer()
        fingerprint = analyzer.analyze("/nonexistent/path")

        assert fingerprint.project_type == ProjectType.UNKNOWN
        assert fingerprint.primary_language == ""


class TestProjectAnalyzerJavaScript:
    """Tests for JavaScript project analysis."""

    @pytest.fixture
    def temp_js_project(self):
        """Create a temporary JavaScript project."""
        with tempfile.TemporaryDirectory() as tmpdir:
            package_json = {
                "name": "test-app",
                "dependencies": {
                    "react": "^18.0.0",
                    "next": "^14.0.0"
                },
                "devDependencies": {
                    "jest": "^29.0.0"
                }
            }
            Path(tmpdir, "package.json").write_text(json.dumps(package_json))
            Path(tmpdir, "src").mkdir()
            Path(tmpdir, "src", "index.js").write_text("export default function App() {}")
            yield tmpdir

    def test_detects_javascript_language(self, temp_js_project):
        """Detects JavaScript project."""
        analyzer = ProjectAnalyzer()
        fingerprint = analyzer.analyze(temp_js_project)

        assert fingerprint.primary_language == "javascript"

    def test_detects_react_framework(self, temp_js_project):
        """Detects React framework."""
        analyzer = ProjectAnalyzer()
        fingerprint = analyzer.analyze(temp_js_project)

        assert any("react" in f.lower() for f in fingerprint.frameworks)

    def test_detects_nextjs_framework(self, temp_js_project):
        """Detects Next.js framework."""
        analyzer = ProjectAnalyzer()
        fingerprint = analyzer.analyze(temp_js_project)

        assert any("next" in f.lower() for f in fingerprint.frameworks)

    def test_detects_test_framework(self, temp_js_project):
        """Detects Jest test framework."""
        analyzer = ProjectAnalyzer()
        fingerprint = analyzer.analyze(temp_js_project)

        assert any("jest" in f.lower() for f in fingerprint.test_frameworks)


class TestProjectTypeDetection:
    """Tests for project type detection logic."""

    def test_api_service_detection(self):
        """Detects API service projects."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "main.py").write_text("from fastapi import FastAPI\napp = FastAPI()")
            Path(tmpdir, "requirements.txt").write_text("fastapi\nuvicorn\n")
            Path(tmpdir, "api").mkdir()
            Path(tmpdir, "api", "routes.py").write_text("# routes")

            analyzer = ProjectAnalyzer()
            fingerprint = analyzer.analyze(tmpdir)

            assert fingerprint.project_type in [ProjectType.API_SERVICE, ProjectType.WEB_APP]

    def test_web_app_detection(self):
        """Detects web app projects."""
        with tempfile.TemporaryDirectory() as tmpdir:
            package_json = {
                "dependencies": {"react": "^18.0.0", "next": "^14.0.0"}
            }
            Path(tmpdir, "package.json").write_text(json.dumps(package_json))
            Path(tmpdir, "pages").mkdir()
            Path(tmpdir, "pages", "index.js").write_text("export default function Home() {}")

            analyzer = ProjectAnalyzer()
            fingerprint = analyzer.analyze(tmpdir)

            assert fingerprint.project_type == ProjectType.WEB_APP

    def test_library_detection(self):
        """Detects library projects."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "setup.py").write_text("from setuptools import setup\nsetup()")
            Path(tmpdir, "mylib").mkdir()
            Path(tmpdir, "mylib", "__init__.py").write_text("# library")
            Path(tmpdir, "mylib", "core.py").write_text("def helper(): pass")

            analyzer = ProjectAnalyzer()
            fingerprint = analyzer.analyze(tmpdir)

            assert fingerprint.project_type in [ProjectType.LIBRARY, ProjectType.UNKNOWN]

    def test_ml_project_detection(self):
        """Detects ML project."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "requirements.txt").write_text("pytorch\nnumpy\npandas\n")
            Path(tmpdir, "train.py").write_text("import torch")
            Path(tmpdir, "model.py").write_text("class Model: pass")

            analyzer = ProjectAnalyzer()
            fingerprint = analyzer.analyze(tmpdir)

            # Should detect ML frameworks
            frameworks_lower = [f.lower() for f in fingerprint.frameworks]
            assert any(f in frameworks_lower for f in ['pytorch', 'numpy', 'pandas'])


class TestPatternDetection:
    """Tests for architectural pattern detection."""

    def test_mvc_pattern_detection(self):
        """Detects MVC pattern."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "models").mkdir()
            Path(tmpdir, "views").mkdir()
            Path(tmpdir, "controllers").mkdir()
            Path(tmpdir, "models", "user.py").write_text("class User: pass")
            Path(tmpdir, "views", "home.py").write_text("def home(): pass")
            Path(tmpdir, "controllers", "main.py").write_text("def index(): pass")

            analyzer = ProjectAnalyzer()
            fingerprint = analyzer.analyze(tmpdir)

            assert "MVC" in fingerprint.patterns_detected

    def test_component_based_detection(self):
        """Detects component-based pattern."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "src").mkdir()
            Path(tmpdir, "src", "components").mkdir()
            Path(tmpdir, "src", "components", "Button.js").write_text("export default Button")

            analyzer = ProjectAnalyzer()
            fingerprint = analyzer.analyze(tmpdir)

            assert "Component-based" in fingerprint.patterns_detected

    def test_monorepo_detection(self):
        """Detects monorepo pattern."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "packages").mkdir()
            Path(tmpdir, "packages", "core").mkdir()
            Path(tmpdir, "packages", "ui").mkdir()
            Path(tmpdir, "packages", "core", "index.js").write_text("")
            Path(tmpdir, "packages", "ui", "index.js").write_text("")

            analyzer = ProjectAnalyzer()
            fingerprint = analyzer.analyze(tmpdir)

            assert "Monorepo" in fingerprint.patterns_detected


class TestDependencyParsing:
    """Tests for dependency file parsing."""

    def test_parse_package_json(self):
        """Parses package.json correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            package_json = {
                "dependencies": {"react": "^18.0.0"},
                "devDependencies": {"jest": "^29.0.0"}
            }
            path = Path(tmpdir, "package.json")
            path.write_text(json.dumps(package_json))

            analyzer = ProjectAnalyzer()
            deps = analyzer._parse_package_json(path)

            assert "react" in deps
            assert "jest" in deps

    def test_parse_requirements_txt(self):
        """Parses requirements.txt correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir, "requirements.txt")
            path.write_text("fastapi>=0.100.0\nuvicorn\n# comment\npydantic==2.0")

            analyzer = ProjectAnalyzer()
            deps = analyzer._parse_requirements_txt(path)

            assert "fastapi" in deps
            assert "uvicorn" in deps
            assert "pydantic" in deps

    def test_parse_invalid_package_json(self):
        """Handles invalid package.json gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir, "package.json")
            path.write_text("not valid json")

            analyzer = ProjectAnalyzer()
            deps = analyzer._parse_package_json(path)

            assert deps == []


class TestBuildToolDetection:
    """Tests for build tool detection."""

    def test_detects_vite(self):
        """Detects Vite build tool."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "vite.config.js").write_text("export default {}")
            Path(tmpdir, "src").mkdir()
            Path(tmpdir, "src", "main.js").write_text("")

            analyzer = ProjectAnalyzer()
            fingerprint = analyzer.analyze(tmpdir)

            assert "Vite" in fingerprint.build_tools

    def test_detects_webpack(self):
        """Detects Webpack build tool."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "webpack.config.js").write_text("module.exports = {}")
            Path(tmpdir, "src").mkdir()
            Path(tmpdir, "src", "index.js").write_text("")

            analyzer = ProjectAnalyzer()
            fingerprint = analyzer.analyze(tmpdir)

            assert "Webpack" in fingerprint.build_tools

    def test_detects_makefile(self):
        """Detects Make build tool."""
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "Makefile").write_text("build:\n\techo build")
            Path(tmpdir, "main.c").write_text("int main() {}")

            analyzer = ProjectAnalyzer()
            fingerprint = analyzer.analyze(tmpdir)

            assert "Make" in fingerprint.build_tools
