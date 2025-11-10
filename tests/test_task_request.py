def test_scheduled_task_with_mocked_requests(mocker, caplog):
    """Test scheduled_task with requests.get() mocked, simulating real API call."""
    from app.tasks import task

    caplog.set_level("INFO")

    import app.config as config
    config.ENV = "production"

    # Prepare mock response
    mock_response = mocker.Mock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "status": "success",
        "result": {"message": "mocked-from-request"}
    }

    mocker.patch("app.task.requests.get", return_value=mock_response)

    # Call the task
    task.scheduled_task()

    assert "API response received and parsed" in caplog.text
    assert "mocked-from-request" in caplog.text
