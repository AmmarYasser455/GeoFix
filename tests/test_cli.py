"""Tests for the GeoFix CLI."""

from click.testing import CliRunner

from geofix.cli import cli


class TestCLI:
    def test_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "GeoFix" in result.output

    def test_version(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        # Check that some version string is present
        assert "version" in result.output.lower()

    def test_analyze_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["analyze", "--help"])
        assert result.exit_code == 0
        assert "auto-fix" in result.output

    def test_validate_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["validate", "--help"])
        assert result.exit_code == 0

    def test_fix_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["fix", "--help"])
        assert result.exit_code == 0

    def test_chat_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, ["chat", "--help"])
        assert result.exit_code == 0
        assert "chat" in result.output.lower()

    def test_no_subcommand_shows_help(self):
        runner = CliRunner()
        result = runner.invoke(cli, [])
        assert result.exit_code == 0
        assert "GeoFix" in result.output
