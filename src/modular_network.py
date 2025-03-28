import numpy as np
import random
import time
import json
import sys
from utils import *
from components import *

class Network:

    def __init__(self, layers, cost: CostFunction = None):
        self.num_layers = len(layers)
        self.layers = layers
        self.cost = cost
        self.mode = Mode.TRAIN
    
    def set_cost(self, cost: CostFunction):
        self.cost = cost

    def set_optimizer(self, optimizer: Optimizer):
        for layer in self.layers:
            # the optimizer object passed into the modular network is more like
            # an optimizer factory, which is why get_optimizer() exists. 
            # this choice was made to allow compartmentalization of layers.
            layer.set_optimizer(optimizer.get_optimizer())
    
    def set_mode(self, mode):
        self.mode = mode
        for layer in self.layers:
            layer.set_mode(mode)
    
    def feedforward(self, a):
        for layer in self.layers:
            a = layer.feedforward(a)
        return a

    def backprop(self, delta):
        for layer in reversed(self.layers):
            delta = layer.backprop(delta)

    def update_mini_batch(self, mini_batch, n, data_augmentation: DataAugmentation):
        """Update the network's weights and biases by applying
        gradient descent using backpropagation to a single mini batch.
        The "mini_batch" is a list of tuples "(x, y)", and "eta"
        is the learning rate."""

        # X is kept as a list of (28, 28) images
        X = np.array([pair[0] for pair in mini_batch])
        # We concatenate Y into a matrix
        Y = np.concatenate([pair[1] for pair in mini_batch], axis=1)

        if data_augmentation is not None:
            X = data_augmentation.fn(X)

        # a^L
        a_L = self.feedforward(X)
        # unscaled delta^L
        delta = self.cost.derivative(a_L, Y)
        # backprop
        self.backprop(delta)

    def train(self, training_data, epochs, mini_batch_size, 
        test_data=None,
        data_augmentation: DataAugmentation = None,
        n_epochs_monitor=1,
        monitor_test_cost=False,
        monitor_test_acc=False,
        monitor_training_cost=False,
        monitor_training_acc=False,
        ):
        """Train the neural network using mini-batch stochastic
        gradient descent.  The "training_data" is a list of tuples
        "(x, y)" representing the training inputs and the desired
        outputs.  The other non-optional parameters are
        self-explanatory.  If "test_data" is provided then the
        network will be evaluated against the test data after each
        epoch, and partial progress printed out.  This is useful for
        tracking progress, but slows things down substantially."""
        self.set_mode(Mode.TRAIN)

        if test_data: 
            n_test = len(test_data)
        
        n = len(training_data)        
        test_cost, test_acc = [], []
        training_cost, training_acc = [], []
        times = []

        curr_time = 0

        for j in range(epochs):
            time1 = time.time()

            random.shuffle(training_data)
            mini_batches = [
                training_data[k:k+mini_batch_size]
                for k in range(0, n, mini_batch_size)]
            
            for mini_batch in mini_batches:
                self.update_mini_batch(mini_batch, len(training_data), data_augmentation)
            
            time2 = time.time()
            print(f"Epoch {j+1} training complete, took {time2 - time1} seconds")
            curr_time += time2 - time1
            
            if (j+1) % n_epochs_monitor == 0:
                times.append(curr_time)
                if monitor_training_cost:
                    cost = self.total_cost(training_data[:10000])
                    training_cost.append(cost)
                    print("Cost on training data: {}".format(cost))
                if monitor_training_acc:
                    accuracy = self.accuracy(training_data[:10000], convert=True)
                    training_acc.append(accuracy)
                    print("Accuracy on training data: {} / {}".format(
                        accuracy, 10000))
                if monitor_test_cost:
                    cost = self.total_cost(test_data, convert=True)
                    test_cost.append(cost)
                    print("Cost on test data: {}".format(cost))
                if monitor_test_acc:
                    accuracy = self.accuracy(test_data)
                    test_acc.append(accuracy)
                    print("Accuracy on test data: {} / {}".format(
                        accuracy, n_test))

        return {"training_acc": training_acc,
                "training_cost": training_cost,
                "test_acc": test_acc,
                "test_cost": test_cost,
                "times": times}

    def accuracy(self, data, convert=False):
        """Return the number of inputs in ``data`` for which the neural
        network outputs the correct result. The neural network's
        output is assumed to be the index of whichever neuron in the
        final layer has the highest activation.

        The flag ``convert`` should be set to False if the data set is
        validation or test data (the usual case), and to True if the
        data set is the training data. The need for this flag arises
        due to differences in the way the results ``y`` are
        represented in the different data sets.  In particular, it
        flags whether we need to convert between the different
        representations.  It may seem strange to use different
        representations for the different data sets.  Why not use the
        same representation for all three data sets?  It's done for
        efficiency reasons -- the program usually evaluates the cost
        on the training data and the accuracy on other data sets.
        These are different types of computations, and using different
        representations speeds things up.  More details on the
        representations can be found in
        mnist_loader.load_data_wrapper.
        """
        prev_mode = self.mode
        self.set_mode(Mode.TEST)
        
        if convert:
            results = [(np.argmax(self.feedforward(np.array([x]))), np.argmax(y))
                       for (x, y) in data]
        else:
            results = [(np.argmax(self.feedforward(np.array([x]))), y)
                        for (x, y) in data]
            
        self.set_mode(prev_mode)
        return sum(int(x == y) for (x, y) in results)
    
    def total_cost(self, data, convert=False, average=True):
        """Return the total cost for the data set ``data``.  The flag
        ``convert`` should be set to False if the data set is the
        training data (the usual case), and to True if the data set is
        the validation or test data.  See comments on the similar (but
        reversed) convention for the ``accuracy`` method, above.
        """
        cost = 0.0
        for x, y in data:
            a = self.feedforward(np.array([x]))
            if convert: 
                y = vectorized_result(y)
            cost += self.cost.fn(a, y)
        for layer in self.layers:
            cost += layer.get_reg_loss()
        if average:
            cost = cost / len(data)
        return cost

    def cost_derivative(self, output_activations, y):
        """Return the vector of partial derivatives \partial C_x /
        \partial a for the output activations."""
        return (output_activations-y)
    
    def save_data(self):
        """Return a dictionary of all the Network's learnables."""
        return {str(i) : layer.save_data() for i, layer in enumerate(self.layers)}

    def save_construction(self):
        """Return this Network's construction dictionary."""
        construction = {str(i) : layer.save_construction() for i, layer in enumerate(self.layers)}
        construction["num_layers"] = self.num_layers
        return construction
    
    def save(self, filename):
        """Save this Network to a file."""
        f = open(filename, "w")
        json.dump({"construction": self.save_construction(),
                   "data": self.save_data()}, f)
        f.close()

    # Helper function for loading nested Components
    def load_object(construction):
        """Process a Component's construction dictionary ``construction`` 
        and return the Component created."""
        targetClass = getattr(sys.modules[__name__], construction["name"])
        params = construction["params"]

        # Duplicate array to avoid changing the Components that created
        # this construction dictionary
        creationParams = []

        # Process nested objects
        for i, param in enumerate(params):
            if isinstance(param, str) and "object>>" in param:
                objectLookupName = param.split("object>>")[1]
                object = Network.load_object(construction[objectLookupName])
                creationParams.append(object)
            else:
                creationParams.append(param)
        
        return targetClass(*creationParams)
        
    def load_architecture(construction):
        """Process a Network's construction dictionary and return
        the Network created."""
        layers = []

        num_layers = construction["num_layers"]
        for i in range(num_layers):
            layers.append(Network.load_object(construction[str(i)]))
        
        return Network(layers)
    
    def load_data(self, data):
        """Load the parameters from the data dictionary ``data``
        onto this network. Requires this network to have the same
        architecture as the saved network."""
        for i, layer in enumerate(self.layers):
            layer.load_data(data[str(i)])

    def load(filename):
        """Load the Network from ``filename`` and return the loaded Network."""
        f = open(filename, "r")
        saved = json.load(f)
        f.close()

        model = Network.load_architecture(saved["construction"])
        model.load_data(saved["data"])

        return model

    # DEPRECATED -- OLD LOADING FUNCTION
    # def load_data_from_file(self, filename):
    #     """Load the parameters from ``filename`` onto this network.
    #     Requires this network to have the same architecture as
    #     the saved network. 
    #     """
    #     f = open(filename, "r")
    #     data = json.load(f)
    #     f.close()

    #     for i, layer in enumerate(self.layers):
    #         layer.load_data(data[str(i)])

