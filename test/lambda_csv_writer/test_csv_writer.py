from lambda_etl.etl.main import lambda_handler

class TestImpl:
    def test_whole_shebang(self, mocker):
        lambda_handler()