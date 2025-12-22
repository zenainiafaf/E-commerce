import unittest
import joblib
import pandas as pd

class TestPrediction(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model = joblib.load("model.pkl")
        cls.label_encoders = joblib.load("label_encoders.pkl")

    def encode_input(self, data):
        for col in data.columns:
            if col in self.label_encoders:
                le = self.label_encoders[col]
                data[col] = data[col].apply(lambda x: le.transform([x])[0] if x in le.classes_ else -1)
        return data

    def test_prediction(self):
        data = pd.DataFrame([{
            'brand': 'Dior',
            'bag style': 'Shoulder Bag',
            'skin type': 'Snake',
            'inner material': 'Cuir',  
            'major color': 'Gris',
            'volume': 250.250,
            'accessories': 'Chain'
        }])
        input_df = self.encode_input(data)
        prediction = self.model.predict(input_df)[0]
        print(f"✅ Prix prédit : {prediction:.2f} $")
        self.assertTrue(prediction > 0)

    def test_prediction_with_rare_value(self):
        data = pd.DataFrame([{
            'brand': 'Chanel',
            'bag style': 'Clutch',
            'skin type': 'Lamb, Python',
            'inner material': 'Cuir',
            'major color': 'Marron',
            'volume': 169.074,
            'accessories': 'Chain'
        }])
        input_df = self.encode_input(data)
        prediction = self.model.predict(input_df)[0]
        print(f"📦 Prix rare : {prediction:.2f} $")
        self.assertTrue(prediction >= 0)

    def test_model_evaluation(self):
        df = pd.read_csv("dataset/clean_data.csv")
        features = ['brand', 'bag style', 'skin type', 'inner material', 'major color', 'volume', 'accessories']
        df = df[features].dropna()

        X_test = df.sample(10, random_state=1).copy()
        for col in features:
            if col in self.label_encoders:
                le = self.label_encoders[col]
                X_test[col] = X_test[col].apply(lambda x: le.transform([x])[0] if x in le.classes_ else -1)

        predictions = self.model.predict(X_test)
        self.assertEqual(len(predictions), 10)

if __name__ == '__main__':
    unittest.main()
