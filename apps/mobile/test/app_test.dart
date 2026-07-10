import 'package:flutter_test/flutter_test.dart';
import 'package:yelisport/app/app.dart';

void main() {
  testWidgets('renders the application shell', (tester) async {
    await tester.pumpWidget(const YeliSportApp());

    expect(find.text('YeliSport'), findsNWidgets(2));
  });
}
