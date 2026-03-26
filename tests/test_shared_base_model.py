from datetime import UTC, datetime

from agent_platform.data_models.base import SharedBaseModel


class ModelTest(SharedBaseModel):
    aware_datetime: datetime
    unaware_datetime: datetime


def test_datetime_model() -> None:
    # Arrange
    test = ModelTest(
        aware_datetime=datetime(2021, 12, 30, 12, 34, 56, tzinfo=UTC),
        unaware_datetime=datetime(2021, 12, 30, 12, 34, 56),
    )

    # Act
    result = test.model_dump()

    # Assert
    assert result["aware_datetime"] == datetime(2021, 12, 30, 12, 34, 56, tzinfo=UTC)
    assert result["unaware_datetime"] == datetime(2021, 12, 30, 12, 34, 56)


def test_camelcase_alias() -> None:
    # Arrange
    class TestModel(SharedBaseModel):
        snake_case_field: str

    # Act
    test = TestModel(snake_case_field="test")
    result = test.model_dump(by_alias=True)

    # Assert
    assert "snakeCaseField" in result
    assert result["snakeCaseField"] == "test"
