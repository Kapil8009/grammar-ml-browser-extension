from backend.app.services.correction import CorrectionService
from tests.fakes import FakeCorrectionModel


def test_service_runs_model_and_builds_suggestions() -> None:
    model = FakeCorrectionModel({"She go to school.": "She goes to school."})
    result = CorrectionService(model).correct("She go to school.")

    assert result.changed is True
    assert result.corrected == "She goes to school."
    assert result.model == "test/fake-gec"
    assert result.suggestions[0].original == "go"
    assert result.suggestions[0].replacement == "goes"


def test_service_keeps_model_output_from_becoming_blank() -> None:
    model = FakeCorrectionModel({"Keep me.": ""})
    result = CorrectionService(model).correct("Keep me.")

    assert result.corrected == "Keep me."
    assert result.changed is False
