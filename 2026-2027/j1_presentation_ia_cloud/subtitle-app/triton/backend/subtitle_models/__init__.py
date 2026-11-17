"""Code of the Triton models (Python backend), shared by the model repository.

Each model directory of ../model_repository holds a config.pbtxt and a one-line
1/model.py that re-exports the TritonPythonModel class from here: the variants
(Whisper sizes) differ only by the parameters of their config.pbtxt.
"""
