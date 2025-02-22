from xai_components.base import InArg, OutArg, InCompArg, Component, xai_component, dynalist, dynatuple

@xai_component
class HelloComponentLibrary(Component):
    """
    Prints a greeting message with the provided string.

    ##### inPorts:
    - input_str (str): The input string to be included in the greeting message.
    """
    input_str: InArg[str]

    def execute(self, ctx) -> None:
        input_str = self.input_str.value
        print("Hello, " + str(input_str))


@xai_component
class InitComponentExample(Component):
    """
    Example of initialization with a default value and conditional handling of input arguments.

    ##### inPorts:
    - input_str (str): The input string to be used in the greeting message.
    - input_int (int): The input integer to be used in the greeting message. If not provided, defaults to 554.
    """
    input_str: InArg[str]
    input_int: InArg[int]

    # method 1 
    def __init__(self):
        super().__init__()
        self.input_str.value = "Default Value!"

    def execute(self, ctx) -> None:
        input_str = self.input_str.value

        # method 2
        input_int = self.input_int.value if self.input_int.value else 554
        
        print("Hello " + input_str)
        print("Hello " + str(input_int))
