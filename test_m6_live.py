#!/usr/bin/env python3
"""
M6 Live Integration Test - Cross-Project Intelligence

This test creates REAL temporary projects, generates learnings,
and verifies they transfer correctly between similar projects.

Run this to prove M6 works end-to-end!

Usage:
    python test_m6_live.py
"""

import sys
import tempfile
import json
import asyncio
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from lib.project_analyzer import ProjectAnalyzer, ProjectFingerprint, ProjectType
from lib.learning_transfer import LearningTransfer, LearningScope
from lib.mind_client import MindClient


def create_fastapi_project(tmpdir: Path) -> Path:
    """Create a realistic FastAPI project."""
    project = tmpdir / "fastapi_app"
    project.mkdir()

    # requirements.txt
    (project / "requirements.txt").write_text("""fastapi>=0.100.0
uvicorn>=0.23.0
sqlalchemy>=2.0.0
pydantic>=2.0.0
pytest>=7.0.0
""")

    # main.py
    (project / "main.py").write_text("""from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session

app = FastAPI()

def get_db():
    pass

@app.get("/")
def read_root():
    return {"Hello": "World"}

@app.get("/users/{user_id}")
def read_user(user_id: int, db: Session = Depends(get_db)):
    return {"user_id": user_id}
""")

    # models.py
    (project / "models.py").write_text("""from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    name = Column(String)
""")

    # tests/
    tests_dir = project / "tests"
    tests_dir.mkdir()
    (tests_dir / "test_main.py").write_text("""import pytest
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)

def test_read_root():
    response = client.get("/")
    assert response.status_code == 200
""")

    return project


def create_react_project(tmpdir: Path) -> Path:
    """Create a realistic React project."""
    project = tmpdir / "react_app"
    project.mkdir()

    # package.json
    (project / "package.json").write_text(json.dumps({
        "name": "react-app",
        "version": "1.0.0",
        "dependencies": {
            "react": "^18.2.0",
            "react-dom": "^18.2.0",
            "next": "^14.0.0"
        },
        "devDependencies": {
            "jest": "^29.0.0",
            "@testing-library/react": "^14.0.0",
            "typescript": "^5.0.0"
        },
        "scripts": {
            "dev": "next dev",
            "build": "next build",
            "test": "jest"
        }
    }, indent=2))

    # src/
    src_dir = project / "src"
    src_dir.mkdir()

    # src/components/
    components_dir = src_dir / "components"
    components_dir.mkdir()

    (components_dir / "Button.tsx").write_text("""import React, { useState } from 'react';

interface ButtonProps {
    label: string;
    onClick: () => void;
}

export const Button: React.FC<ButtonProps> = ({ label, onClick }) => {
    const [clicked, setClicked] = useState(false);

    return (
        <button onClick={() => { setClicked(true); onClick(); }}>
            {label}
        </button>
    );
};
""")

    # pages/
    pages_dir = project / "pages"
    pages_dir.mkdir()
    (pages_dir / "index.tsx").write_text("""export default function Home() {
    return <div>Hello Next.js</div>;
}
""")

    return project


def create_cli_project(tmpdir: Path) -> Path:
    """Create a realistic CLI tool project."""
    project = tmpdir / "cli_tool"
    project.mkdir()

    # requirements.txt
    (project / "requirements.txt").write_text("""click>=8.0.0
rich>=13.0.0
typer>=0.9.0
""")

    # cli.py
    (project / "cli.py").write_text("""import click
from rich.console import Console

console = Console()

@click.group()
def cli():
    '''My CLI Tool'''
    pass

@cli.command()
@click.argument('name')
def greet(name: str):
    '''Greet someone'''
    console.print(f"[green]Hello, {name}![/green]")

@cli.command()
@click.option('--verbose', '-v', is_flag=True)
def status(verbose: bool):
    '''Show status'''
    console.print("[blue]Status: OK[/blue]")

if __name__ == '__main__':
    cli()
""")

    # setup.py
    (project / "setup.py").write_text("""from setuptools import setup

setup(
    name='my-cli-tool',
    version='1.0.0',
    py_modules=['cli'],
    entry_points={
        'console_scripts': [
            'mycli=cli:cli',
        ],
    },
)
""")

    return project


def create_ml_project(tmpdir: Path) -> Path:
    """Create a realistic ML project."""
    project = tmpdir / "ml_project"
    project.mkdir()

    # requirements.txt
    (project / "requirements.txt").write_text("""torch>=2.0.0
numpy>=1.24.0
pandas>=2.0.0
scikit-learn>=1.3.0
matplotlib>=3.7.0
""")

    # train.py
    (project / "train.py").write_text("""import torch
import torch.nn as nn
import numpy as np
from torch.utils.data import DataLoader

class SimpleModel(nn.Module):
    def __init__(self, input_size, hidden_size, output_size):
        super().__init__()
        self.fc1 = nn.Linear(input_size, hidden_size)
        self.fc2 = nn.Linear(hidden_size, output_size)

    def forward(self, x):
        x = torch.relu(self.fc1(x))
        return self.fc2(x)

def train_model(model, dataloader, epochs=10):
    optimizer = torch.optim.Adam(model.parameters())
    criterion = nn.MSELoss()

    for epoch in range(epochs):
        for batch in dataloader:
            optimizer.zero_grad()
            loss = criterion(model(batch[0]), batch[1])
            loss.backward()
            optimizer.step()
""")

    # data/
    data_dir = project / "data"
    data_dir.mkdir()

    # models/
    models_dir = project / "models"
    models_dir.mkdir()

    return project


def print_header(text: str):
    """Print a formatted header."""
    print()
    print("=" * 70)
    print(f"  {text}")
    print("=" * 70)


def print_subheader(text: str):
    """Print a formatted subheader."""
    print()
    print(f"  --- {text} ---")


def print_result(passed: bool, message: str):
    """Print a test result."""
    status = "[PASS]" if passed else "[FAIL]"
    print(f"  {status} {message}")


async def run_tests():
    """Run all M6 integration tests."""
    print_header("M6 LIVE INTEGRATION TEST - Cross-Project Intelligence")

    analyzer = ProjectAnalyzer()
    transfer = LearningTransfer()

    # Check Mind connection
    mind = MindClient()
    mind_available = await mind.is_available()
    print(f"\n  Mind Status: {'Connected' if mind_available else 'Offline (tests will still run)'}")

    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)

        # ============================================
        # PHASE 1: Create Test Projects
        # ============================================
        print_header("PHASE 1: Creating Test Projects")

        fastapi_project = create_fastapi_project(tmpdir)
        print(f"  Created: FastAPI project at {fastapi_project.name}")

        react_project = create_react_project(tmpdir)
        print(f"  Created: React project at {react_project.name}")

        cli_project = create_cli_project(tmpdir)
        print(f"  Created: CLI tool project at {cli_project.name}")

        ml_project = create_ml_project(tmpdir)
        print(f"  Created: ML project at {ml_project.name}")

        # ============================================
        # PHASE 2: Analyze Projects
        # ============================================
        print_header("PHASE 2: Analyzing Projects")

        fastapi_fp = analyzer.analyze(str(fastapi_project))
        react_fp = analyzer.analyze(str(react_project))
        cli_fp = analyzer.analyze(str(cli_project))
        ml_fp = analyzer.analyze(str(ml_project))

        results = []

        # Test FastAPI detection
        passed = fastapi_fp.project_type == ProjectType.API_SERVICE
        results.append(passed)
        print_result(passed, f"FastAPI detected as: {fastapi_fp.project_type.value} (expected: api_service)")
        print(f"        Language: {fastapi_fp.primary_language}, Frameworks: {fastapi_fp.frameworks}")

        # Test React detection
        passed = react_fp.project_type == ProjectType.WEB_APP
        results.append(passed)
        print_result(passed, f"React detected as: {react_fp.project_type.value} (expected: web_app)")
        print(f"        Language: {react_fp.primary_language}, Frameworks: {react_fp.frameworks}")

        # Test CLI detection
        passed = cli_fp.primary_language == "python"
        results.append(passed)
        print_result(passed, f"CLI detected as: {cli_fp.project_type.value}, Language: {cli_fp.primary_language}")

        # Test ML detection
        passed = ml_fp.project_type == ProjectType.ML_PROJECT or "PyTorch" in ml_fp.frameworks
        results.append(passed)
        print_result(passed, f"ML detected as: {ml_fp.project_type.value}, Frameworks: {ml_fp.frameworks}")

        # ============================================
        # PHASE 3: Test Similarity Scores
        # ============================================
        print_header("PHASE 3: Testing Similarity Scores")

        # FastAPI vs itself should be ~1.0
        self_sim = fastapi_fp.similarity(fastapi_fp)
        passed = self_sim > 0.95
        results.append(passed)
        print_result(passed, f"FastAPI self-similarity: {self_sim:.0%} (expected: ~100%)")

        # FastAPI vs React should be low (different languages, different types)
        cross_sim = fastapi_fp.similarity(react_fp)
        passed = cross_sim < 0.5
        results.append(passed)
        print_result(passed, f"FastAPI vs React: {cross_sim:.0%} (expected: <50%)")

        # FastAPI vs CLI should be medium (same language, different type)
        python_sim = fastapi_fp.similarity(cli_fp)
        passed = 0.2 < python_sim < 0.7
        results.append(passed)
        print_result(passed, f"FastAPI vs CLI: {python_sim:.0%} (expected: 20-70%)")

        # ============================================
        # PHASE 4: Create Learnings with Different Scopes
        # ============================================
        print_header("PHASE 4: Creating Learnings with Different Scopes")

        # Universal learning (applies everywhere)
        universal = transfer.annotate_learning(
            learning_id="grep_effective",
            content="TOOL_EFFECTIVENESS: Grep has 93% success rate for code search",
            source_fingerprint=fastapi_fp,
            metadata={"pattern_type": "tool_effectiveness", "confidence": 0.93}
        )
        passed = universal.scope == LearningScope.UNIVERSAL
        results.append(passed)
        print_result(passed, f"Universal learning scope: {universal.scope.value}")

        # Python-specific learning
        python_learning = transfer.annotate_learning(
            learning_id="pytest_fixtures",
            content="Use pytest fixtures for Python test setup with dependency injection",
            source_fingerprint=fastapi_fp,
            metadata={"confidence": 0.85}
        )
        passed = python_learning.scope == LearningScope.LANGUAGE
        results.append(passed)
        print_result(passed, f"Python learning scope: {python_learning.scope.value}, languages: {python_learning.applicable_languages}")

        # FastAPI-specific learning
        fastapi_learning = transfer.annotate_learning(
            learning_id="fastapi_depends",
            content="Use Depends() for FastAPI dependency injection in route handlers",
            source_fingerprint=fastapi_fp,
            metadata={"confidence": 0.88}
        )
        passed = fastapi_learning.scope == LearningScope.FRAMEWORK
        results.append(passed)
        print_result(passed, f"FastAPI learning scope: {fastapi_learning.scope.value}, frameworks: {fastapi_learning.applicable_frameworks}")

        # React-specific learning
        react_learning = transfer.annotate_learning(
            learning_id="react_hooks",
            content="Use useState and useEffect hooks for React component state management",
            source_fingerprint=react_fp,
            metadata={"confidence": 0.9}
        )
        passed = react_learning.scope == LearningScope.FRAMEWORK
        results.append(passed)
        print_result(passed, f"React learning scope: {react_learning.scope.value}, frameworks: {react_learning.applicable_frameworks}")

        # ============================================
        # PHASE 5: Test Learning Transfer
        # ============================================
        print_header("PHASE 5: Testing Learning Transfer")

        print_subheader("Learnings applicable to FastAPI project")
        fastapi_learnings = transfer.get_applicable_learnings(fastapi_fp)
        print(f"  Found {len(fastapi_learnings)} applicable learnings:")
        for l in fastapi_learnings:
            print(f"    - [{l.scope.value}] {l.learning_id}")

        # FastAPI should get: universal + python + fastapi (NOT react)
        has_universal = any(l.learning_id == "grep_effective" for l in fastapi_learnings)
        has_python = any(l.learning_id == "pytest_fixtures" for l in fastapi_learnings)
        has_fastapi = any(l.learning_id == "fastapi_depends" for l in fastapi_learnings)
        has_react = any(l.learning_id == "react_hooks" for l in fastapi_learnings)

        passed = has_universal
        results.append(passed)
        print_result(passed, "FastAPI gets universal learning")

        passed = has_python
        results.append(passed)
        print_result(passed, "FastAPI gets Python learning")

        passed = has_fastapi
        results.append(passed)
        print_result(passed, "FastAPI gets FastAPI-specific learning")

        passed = not has_react
        results.append(passed)
        print_result(passed, "FastAPI does NOT get React learning")

        print_subheader("Learnings applicable to React project")
        react_learnings = transfer.get_applicable_learnings(react_fp)
        print(f"  Found {len(react_learnings)} applicable learnings:")
        for l in react_learnings:
            print(f"    - [{l.scope.value}] {l.learning_id}")

        # React should get: universal + react (NOT python, NOT fastapi)
        has_universal = any(l.learning_id == "grep_effective" for l in react_learnings)
        has_python = any(l.learning_id == "pytest_fixtures" for l in react_learnings)
        has_fastapi = any(l.learning_id == "fastapi_depends" for l in react_learnings)
        has_react = any(l.learning_id == "react_hooks" for l in react_learnings)

        passed = has_universal
        results.append(passed)
        print_result(passed, "React gets universal learning")

        passed = not has_python
        results.append(passed)
        print_result(passed, "React does NOT get Python learning")

        passed = not has_fastapi
        results.append(passed)
        print_result(passed, "React does NOT get FastAPI learning")

        passed = has_react
        results.append(passed)
        print_result(passed, "React gets React-specific learning")

        print_subheader("Learnings applicable to CLI project")
        cli_learnings = transfer.get_applicable_learnings(cli_fp)
        print(f"  Found {len(cli_learnings)} applicable learnings:")
        for l in cli_learnings:
            print(f"    - [{l.scope.value}] {l.learning_id}")

        # CLI should get: universal + python (NOT fastapi, NOT react)
        has_universal = any(l.learning_id == "grep_effective" for l in cli_learnings)
        has_python = any(l.learning_id == "pytest_fixtures" for l in cli_learnings)
        has_fastapi = any(l.learning_id == "fastapi_depends" for l in cli_learnings)

        passed = has_universal
        results.append(passed)
        print_result(passed, "CLI gets universal learning")

        passed = has_python
        results.append(passed)
        print_result(passed, "CLI gets Python learning")

        passed = not has_fastapi
        results.append(passed)
        print_result(passed, "CLI does NOT get FastAPI learning")

        # ============================================
        # PHASE 6: Test Confidence Adjustment
        # ============================================
        print_header("PHASE 6: Testing Confidence Adjustment")

        # Transfer to similar project should have higher confidence
        fastapi2 = ProjectFingerprint(
            project_path="/other_fastapi",
            project_type=ProjectType.API_SERVICE,
            primary_language="python",
            frameworks=["FastAPI"],
            file_count=50
        )

        conf_similar = transfer.calculate_transfer_confidence(
            fastapi_learning, fastapi_fp, fastapi2
        )
        conf_different = transfer.calculate_transfer_confidence(
            fastapi_learning, fastapi_fp, react_fp
        )

        passed = conf_similar > conf_different
        results.append(passed)
        print_result(passed, f"Similar project confidence ({conf_similar:.0%}) > different ({conf_different:.0%})")

        # ============================================
        # PHASE 7: Test Transfer Outcome Recording
        # ============================================
        print_header("PHASE 7: Testing Transfer Outcome Recording")

        initial_conf = universal.transfer_confidence

        # Record success
        transfer.record_transfer_outcome("grep_effective", True)
        after_success = transfer.transferable_learnings["grep_effective"].transfer_confidence
        passed = after_success > initial_conf
        results.append(passed)
        print_result(passed, f"Confidence after success: {initial_conf:.0%} -> {after_success:.0%}")

        # Record failure
        transfer.record_transfer_outcome("grep_effective", False)
        after_failure = transfer.transferable_learnings["grep_effective"].transfer_confidence
        passed = after_failure < after_success
        results.append(passed)
        print_result(passed, f"Confidence after failure: {after_success:.0%} -> {after_failure:.0%}")

        # ============================================
        # FINAL SUMMARY
        # ============================================
        print_header("FINAL SUMMARY")

        passed_count = sum(results)
        total_count = len(results)

        print(f"\n  Tests Passed: {passed_count}/{total_count}")
        print(f"  Success Rate: {passed_count/total_count:.0%}")
        print()

        if passed_count == total_count:
            print("  " + "=" * 50)
            print("  |  ALL TESTS PASSED - M6 IS FULLY OPERATIONAL!  |")
            print("  " + "=" * 50)
        else:
            print(f"  WARNING: {total_count - passed_count} tests failed")

        print()

        stats = transfer.get_stats()
        print("  Transfer System Stats:")
        print(f"    Total learnings: {stats['total_learnings']}")
        print(f"    By scope: {stats['by_scope']}")
        print(f"    Total transfers: {stats['total_transfers']}")
        print(f"    Transfer success rate: {stats['transfer_success_rate']:.0%}")

    await mind.close()
    print()

    return passed_count == total_count


if __name__ == "__main__":
    success = asyncio.run(run_tests())
    sys.exit(0 if success else 1)
