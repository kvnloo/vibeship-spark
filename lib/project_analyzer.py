"""
Spark Project Analyzer: Fingerprint projects for cross-project intelligence.

Analyzes a project to detect:
- Languages from file extensions and config files
- Frameworks from dependencies and imports
- Project type from structure and dependencies
- Patterns from directory layout

This enables sharing learnings across similar projects.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set
from pathlib import Path
from enum import Enum
import json
import re


class ProjectType(Enum):
    """High-level project classification."""
    WEB_APP = "web_app"
    CLI_TOOL = "cli_tool"
    LIBRARY = "library"
    API_SERVICE = "api_service"
    DATA_PIPELINE = "data_pipeline"
    ML_PROJECT = "ml_project"
    MOBILE_APP = "mobile_app"
    UNKNOWN = "unknown"


@dataclass
class ProjectFingerprint:
    """Fingerprint capturing project characteristics."""
    project_path: str
    project_type: ProjectType
    primary_language: str
    languages: List[str] = field(default_factory=list)
    frameworks: List[str] = field(default_factory=list)
    build_tools: List[str] = field(default_factory=list)
    test_frameworks: List[str] = field(default_factory=list)
    patterns_detected: List[str] = field(default_factory=list)
    file_count: int = 0
    directory_structure: Dict[str, int] = field(default_factory=dict)

    def similarity(self, other: 'ProjectFingerprint') -> float:
        """
        Calculate similarity score between 0 and 1.

        Factors:
        - Same project type: +0.3
        - Same primary language: +0.2
        - Overlapping frameworks: +0.2 * overlap ratio (or +0.2 if both empty)
        - Overlapping patterns: +0.2 * overlap ratio (or +0.2 if both empty)
        - Similar size: +0.1
        """
        score = 0.0

        # Same project type: +0.3
        if self.project_type == other.project_type:
            score += 0.3

        # Same primary language: +0.2
        if self.primary_language == other.primary_language:
            score += 0.2

        # Overlapping frameworks: +0.2 * overlap ratio
        if self.frameworks or other.frameworks:
            self_set = set(f.lower() for f in self.frameworks)
            other_set = set(f.lower() for f in other.frameworks)
            if self_set and other_set:
                overlap = len(self_set & other_set)
                total = len(self_set | other_set)
                score += 0.2 * (overlap / total) if total > 0 else 0
            elif not self_set and not other_set:
                # Both empty - consider equal
                score += 0.2
        else:
            # Both empty
            score += 0.2

        # Overlapping patterns: +0.2 * overlap ratio
        if self.patterns_detected or other.patterns_detected:
            self_set = set(self.patterns_detected)
            other_set = set(other.patterns_detected)
            if self_set and other_set:
                overlap = len(self_set & other_set)
                total = len(self_set | other_set)
                score += 0.2 * (overlap / total) if total > 0 else 0
            elif not self_set and not other_set:
                score += 0.2
        else:
            score += 0.2

        # Similar size: +0.1
        if self.file_count > 0 and other.file_count > 0:
            ratio = min(self.file_count, other.file_count) / max(self.file_count, other.file_count)
            score += 0.1 * ratio
        elif self.file_count == other.file_count:
            # Both zero or equal
            score += 0.1

        return min(score, 1.0)

    def to_dict(self) -> Dict:
        """Convert to dictionary for storage."""
        return {
            "project_path": self.project_path,
            "project_type": self.project_type.value,
            "primary_language": self.primary_language,
            "languages": self.languages,
            "frameworks": self.frameworks,
            "build_tools": self.build_tools,
            "test_frameworks": self.test_frameworks,
            "patterns_detected": self.patterns_detected,
            "file_count": self.file_count,
            "directory_structure": self.directory_structure
        }

    @classmethod
    def from_dict(cls, data: Dict) -> 'ProjectFingerprint':
        """Create from dictionary."""
        return cls(
            project_path=data.get("project_path", ""),
            project_type=ProjectType(data.get("project_type", "unknown")),
            primary_language=data.get("primary_language", ""),
            languages=data.get("languages", []),
            frameworks=data.get("frameworks", []),
            build_tools=data.get("build_tools", []),
            test_frameworks=data.get("test_frameworks", []),
            patterns_detected=data.get("patterns_detected", []),
            file_count=data.get("file_count", 0),
            directory_structure=data.get("directory_structure", {})
        )


class ProjectAnalyzer:
    """
    Analyzes a project to create its fingerprint.

    Detects:
    - Languages from file extensions and config files
    - Frameworks from dependencies and imports
    - Project type from structure and dependencies
    - Patterns from directory layout
    """

    # File patterns for detection
    LANGUAGE_EXTENSIONS = {
        '.py': 'python',
        '.js': 'javascript',
        '.jsx': 'javascript',
        '.ts': 'typescript',
        '.tsx': 'typescript',
        '.go': 'go',
        '.rs': 'rust',
        '.java': 'java',
        '.rb': 'ruby',
        '.cpp': 'cpp',
        '.c': 'c',
        '.cs': 'csharp',
        '.php': 'php',
        '.swift': 'swift',
        '.kt': 'kotlin',
    }

    CONFIG_FILES = {
        'package.json': 'javascript',
        'requirements.txt': 'python',
        'pyproject.toml': 'python',
        'setup.py': 'python',
        'go.mod': 'go',
        'Cargo.toml': 'rust',
        'pom.xml': 'java',
        'build.gradle': 'java',
        'Gemfile': 'ruby',
        'composer.json': 'php',
    }

    FRAMEWORK_INDICATORS = {
        # Python frameworks
        'fastapi': ('python', 'FastAPI'),
        'django': ('python', 'Django'),
        'flask': ('python', 'Flask'),
        'streamlit': ('python', 'Streamlit'),
        'pytorch': ('python', 'PyTorch'),
        'tensorflow': ('python', 'TensorFlow'),
        'pandas': ('python', 'Pandas'),
        'numpy': ('python', 'NumPy'),
        'sqlalchemy': ('python', 'SQLAlchemy'),
        'pytest': ('python', 'pytest'),
        # JavaScript frameworks
        'react': ('javascript', 'React'),
        'vue': ('javascript', 'Vue'),
        'angular': ('javascript', 'Angular'),
        'express': ('javascript', 'Express'),
        'next': ('javascript', 'Next.js'),
        'nuxt': ('javascript', 'Nuxt'),
        'svelte': ('javascript', 'Svelte'),
        'nest': ('javascript', 'NestJS'),
        'jest': ('javascript', 'Jest'),
        # Other
        'gin': ('go', 'Gin'),
        'actix': ('rust', 'Actix'),
        'spring': ('java', 'Spring'),
        'rails': ('ruby', 'Rails'),
    }

    BUILD_TOOLS = {
        'webpack': 'Webpack',
        'vite': 'Vite',
        'rollup': 'Rollup',
        'esbuild': 'esbuild',
        'parcel': 'Parcel',
        'gulp': 'Gulp',
        'grunt': 'Grunt',
        'make': 'Make',
        'cmake': 'CMake',
        'maven': 'Maven',
        'gradle': 'Gradle',
        'cargo': 'Cargo',
        'pip': 'pip',
        'poetry': 'Poetry',
    }

    TEST_FRAMEWORKS = {
        'pytest': 'pytest',
        'unittest': 'unittest',
        'jest': 'Jest',
        'mocha': 'Mocha',
        'jasmine': 'Jasmine',
        'vitest': 'Vitest',
        'rspec': 'RSpec',
        'junit': 'JUnit',
        'go test': 'Go Test',
    }

    # Directories to skip
    SKIP_DIRS = {
        'node_modules', '.git', '__pycache__', '.venv', 'venv',
        'env', '.env', 'dist', 'build', '.next', '.nuxt',
        'target', 'vendor', '.idea', '.vscode', 'coverage',
        '.pytest_cache', '.mypy_cache', 'egg-info'
    }

    def __init__(self, max_files_to_scan: int = 1000):
        self.max_files_to_scan = max_files_to_scan

    def analyze(self, project_path: str) -> ProjectFingerprint:
        """
        Analyze a project and return its fingerprint.

        Args:
            project_path: Path to project root

        Returns:
            ProjectFingerprint with detected characteristics
        """
        path = Path(project_path)
        if not path.exists():
            return ProjectFingerprint(
                project_path=project_path,
                project_type=ProjectType.UNKNOWN,
                primary_language=""
            )

        # Detect components
        languages = self._detect_languages(path)
        primary_language = languages[0] if languages else ""
        frameworks = self._detect_frameworks(path, languages)
        build_tools = self._detect_build_tools(path)
        test_frameworks = self._detect_test_frameworks(path, languages)
        project_type = self._detect_project_type(path, languages, frameworks)
        patterns = self._detect_patterns(path)
        dir_structure = self._analyze_structure(path)
        file_count = sum(dir_structure.values())

        return ProjectFingerprint(
            project_path=project_path,
            project_type=project_type,
            primary_language=primary_language,
            languages=languages,
            frameworks=frameworks,
            build_tools=build_tools,
            test_frameworks=test_frameworks,
            patterns_detected=patterns,
            file_count=file_count,
            directory_structure=dir_structure
        )

    def _detect_languages(self, project_path: Path) -> List[str]:
        """Detect programming languages used."""
        language_counts: Dict[str, int] = {}

        # Check config files first
        for config_file, language in self.CONFIG_FILES.items():
            if (project_path / config_file).exists():
                language_counts[language] = language_counts.get(language, 0) + 10

        # Count file extensions
        files_scanned = 0
        for file_path in self._iter_files(project_path):
            if files_scanned >= self.max_files_to_scan:
                break
            ext = file_path.suffix.lower()
            if ext in self.LANGUAGE_EXTENSIONS:
                lang = self.LANGUAGE_EXTENSIONS[ext]
                language_counts[lang] = language_counts.get(lang, 0) + 1
            files_scanned += 1

        # Sort by count
        sorted_langs = sorted(language_counts.items(), key=lambda x: x[1], reverse=True)
        return [lang for lang, _ in sorted_langs]

    def _detect_frameworks(self, project_path: Path, languages: List[str]) -> List[str]:
        """Detect frameworks from dependencies."""
        frameworks: Set[str] = set()

        # Check package.json
        package_json = project_path / "package.json"
        if package_json.exists():
            deps = self._parse_package_json(package_json)
            for dep in deps:
                dep_lower = dep.lower()
                for indicator, (lang, framework) in self.FRAMEWORK_INDICATORS.items():
                    if indicator in dep_lower:
                        frameworks.add(framework)

        # Check requirements.txt
        requirements_txt = project_path / "requirements.txt"
        if requirements_txt.exists():
            deps = self._parse_requirements_txt(requirements_txt)
            for dep in deps:
                dep_lower = dep.lower()
                for indicator, (lang, framework) in self.FRAMEWORK_INDICATORS.items():
                    if indicator in dep_lower:
                        frameworks.add(framework)

        # Check pyproject.toml
        pyproject = project_path / "pyproject.toml"
        if pyproject.exists():
            deps = self._parse_pyproject_toml(pyproject)
            for dep in deps:
                dep_lower = dep.lower()
                for indicator, (lang, framework) in self.FRAMEWORK_INDICATORS.items():
                    if indicator in dep_lower:
                        frameworks.add(framework)

        return list(frameworks)

    def _detect_build_tools(self, project_path: Path) -> List[str]:
        """Detect build tools used."""
        tools: Set[str] = set()

        # Check for build config files
        build_files = {
            'webpack.config.js': 'Webpack',
            'vite.config.js': 'Vite',
            'vite.config.ts': 'Vite',
            'rollup.config.js': 'Rollup',
            'gulpfile.js': 'Gulp',
            'Gruntfile.js': 'Grunt',
            'Makefile': 'Make',
            'CMakeLists.txt': 'CMake',
            'Cargo.toml': 'Cargo',
            'pyproject.toml': 'Poetry',
        }

        for filename, tool in build_files.items():
            if (project_path / filename).exists():
                tools.add(tool)

        # Check package.json scripts
        package_json = project_path / "package.json"
        if package_json.exists():
            try:
                with open(package_json) as f:
                    data = json.load(f)
                    scripts = data.get("scripts", {})
                    scripts_str = " ".join(scripts.values()).lower()
                    for tool_key, tool_name in self.BUILD_TOOLS.items():
                        if tool_key in scripts_str:
                            tools.add(tool_name)
            except (json.JSONDecodeError, IOError):
                pass

        return list(tools)

    def _detect_test_frameworks(self, project_path: Path, languages: List[str]) -> List[str]:
        """Detect test frameworks."""
        frameworks: Set[str] = set()

        # Check for test directories
        test_dirs = ['tests', 'test', '__tests__', 'spec', 'specs']
        for test_dir in test_dirs:
            if (project_path / test_dir).exists():
                # Infer from language
                if 'python' in languages:
                    frameworks.add('pytest')
                if 'javascript' in languages or 'typescript' in languages:
                    frameworks.add('Jest')

        # Check package.json for test deps
        package_json = project_path / "package.json"
        if package_json.exists():
            try:
                with open(package_json) as f:
                    data = json.load(f)
                    all_deps = {
                        **data.get("dependencies", {}),
                        **data.get("devDependencies", {})
                    }
                    for dep in all_deps:
                        dep_lower = dep.lower()
                        for indicator, framework in self.TEST_FRAMEWORKS.items():
                            if indicator in dep_lower:
                                frameworks.add(framework)
            except (json.JSONDecodeError, IOError):
                pass

        # Check for pytest.ini or setup.cfg
        if (project_path / "pytest.ini").exists() or (project_path / "setup.cfg").exists():
            frameworks.add('pytest')

        return list(frameworks)

    def _detect_project_type(
        self,
        project_path: Path,
        languages: List[str],
        frameworks: List[str]
    ) -> ProjectType:
        """Infer project type from characteristics."""
        frameworks_lower = [f.lower() for f in frameworks]

        # Web app indicators
        web_frameworks = ['react', 'vue', 'angular', 'svelte', 'next.js', 'nuxt']
        if any(f in frameworks_lower for f in web_frameworks):
            return ProjectType.WEB_APP

        # API service indicators
        api_frameworks = ['fastapi', 'flask', 'django', 'express', 'nestjs', 'gin', 'actix', 'spring']
        if any(f in frameworks_lower for f in api_frameworks):
            # Check for frontend
            if (project_path / "src" / "components").exists() or (project_path / "pages").exists():
                return ProjectType.WEB_APP
            return ProjectType.API_SERVICE

        # CLI tool indicators
        cli_indicators = ['click', 'argparse', 'typer', 'commander', 'yargs']
        if any(ind in " ".join(frameworks_lower) for ind in cli_indicators):
            return ProjectType.CLI_TOOL

        # ML project indicators
        ml_frameworks = ['pytorch', 'tensorflow', 'keras', 'scikit-learn', 'pandas', 'numpy']
        if any(f in frameworks_lower for f in ml_frameworks):
            return ProjectType.ML_PROJECT

        # Library indicators - has setup.py or is mostly source code
        if (project_path / "setup.py").exists() or (project_path / "pyproject.toml").exists():
            if not any((project_path / d).exists() for d in ['app', 'api', 'src/pages', 'pages']):
                return ProjectType.LIBRARY

        # Data pipeline indicators
        pipeline_dirs = ['dags', 'pipelines', 'etl', 'data']
        if any((project_path / d).exists() for d in pipeline_dirs):
            if 'airflow' in " ".join(frameworks_lower) or (project_path / "dags").exists():
                return ProjectType.DATA_PIPELINE

        # Mobile app indicators
        mobile_indicators = ['ios', 'android', 'react-native', 'flutter', 'expo']
        if any(ind in " ".join(frameworks_lower) for ind in mobile_indicators):
            return ProjectType.MOBILE_APP

        return ProjectType.UNKNOWN

    def _detect_patterns(self, project_path: Path) -> List[str]:
        """Detect architectural patterns from structure."""
        patterns: Set[str] = set()

        # MVC pattern
        mvc_dirs = ['models', 'views', 'controllers']
        if sum((project_path / d).exists() for d in mvc_dirs) >= 2:
            patterns.add('MVC')

        # Component-based
        if (project_path / "components").exists() or (project_path / "src" / "components").exists():
            patterns.add('Component-based')

        # Microservices
        if (project_path / "services").exists():
            services_dir = project_path / "services"
            if services_dir.is_dir() and len(list(services_dir.iterdir())) > 1:
                patterns.add('Microservices')

        # Monorepo
        if (project_path / "packages").exists() or (project_path / "apps").exists():
            patterns.add('Monorepo')

        # Domain-driven design
        ddd_dirs = ['domain', 'infrastructure', 'application', 'interfaces']
        if sum((project_path / d).exists() for d in ddd_dirs) >= 2:
            patterns.add('DDD')

        # Clean architecture
        clean_dirs = ['entities', 'usecases', 'adapters', 'frameworks']
        if sum((project_path / d).exists() for d in clean_dirs) >= 2:
            patterns.add('Clean Architecture')

        # API-first
        if (project_path / "openapi.yaml").exists() or (project_path / "swagger.json").exists():
            patterns.add('API-first')

        # Test-driven (has extensive tests)
        test_dirs = ['tests', 'test', '__tests__', 'spec']
        for test_dir in test_dirs:
            test_path = project_path / test_dir
            if test_path.exists() and test_path.is_dir():
                test_files = list(test_path.rglob("*test*.py")) + list(test_path.rglob("*.test.*"))
                if len(test_files) > 5:
                    patterns.add('Test-heavy')
                    break

        return list(patterns)

    def _analyze_structure(self, project_path: Path) -> Dict[str, int]:
        """Analyze directory structure."""
        structure: Dict[str, int] = {}

        try:
            # Count files in root directory
            root_files = sum(1 for item in project_path.iterdir() if item.is_file())
            if root_files > 0:
                structure["."] = root_files

            # Count files in subdirectories
            for item in project_path.iterdir():
                if item.is_dir() and item.name not in self.SKIP_DIRS and not item.name.startswith('.'):
                    count = sum(1 for _ in self._iter_files(item))
                    if count > 0:
                        structure[item.name] = count
        except PermissionError:
            pass

        return structure

    def _iter_files(self, directory: Path):
        """Iterate over files, skipping common non-source directories."""
        try:
            for item in directory.iterdir():
                if item.is_file():
                    yield item
                elif item.is_dir() and item.name not in self.SKIP_DIRS and not item.name.startswith('.'):
                    yield from self._iter_files(item)
        except PermissionError:
            pass

    def _parse_package_json(self, path: Path) -> List[str]:
        """Parse package.json for dependencies."""
        try:
            with open(path) as f:
                data = json.load(f)
                deps = list(data.get("dependencies", {}).keys())
                deps += list(data.get("devDependencies", {}).keys())
                return deps
        except (json.JSONDecodeError, IOError):
            return []

    def _parse_requirements_txt(self, path: Path) -> List[str]:
        """Parse requirements.txt for dependencies."""
        try:
            deps = []
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        # Extract package name (before any version specifier)
                        match = re.match(r'^([a-zA-Z0-9_-]+)', line)
                        if match:
                            deps.append(match.group(1))
            return deps
        except IOError:
            return []

    def _parse_pyproject_toml(self, path: Path) -> List[str]:
        """Parse pyproject.toml for dependencies."""
        try:
            deps = []
            with open(path) as f:
                content = f.read()
                # Simple regex to find dependencies
                # Look for dependencies = [...] or [project.dependencies]
                dep_matches = re.findall(r'"([a-zA-Z0-9_-]+)', content)
                deps.extend(dep_matches)
            return deps
        except IOError:
            return []
