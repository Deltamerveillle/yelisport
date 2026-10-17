import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:yelisport/core/localization/generated/app_localizations.dart';
import 'package:yelisport/features/auth/presentation/auth_providers.dart';
import 'package:yelisport/features/auth/presentation/sign_in_screen.dart';
import 'package:yelisport/features/sms_connect/domain/sms_connect_models.dart';
import 'package:yelisport/features/sms_connect/presentation/sms_connect_providers.dart';

String _typeLabel(AppLocalizations l10n, InterestType type) => switch (type) {
      InterestType.trial => l10n.smsConnectTrial,
      InterestType.recruitment => l10n.smsConnectRecruitment,
      InterestType.contract => l10n.smsConnectContract,
      InterestType.partnership => l10n.smsConnectPartnership,
      InterestType.information => l10n.smsConnectInformation,
    };

String _statusLabel(AppLocalizations l10n, OpportunityStatus status) =>
    switch (status) {
      OpportunityStatus.active => l10n.smsConnectActive,
      OpportunityStatus.progressing => l10n.smsConnectProgressing,
      OpportunityStatus.successful => l10n.smsConnectSuccessful,
      OpportunityStatus.unsuccessful => l10n.smsConnectUnsuccessful,
      OpportunityStatus.withdrawn => l10n.smsConnectWithdrawn,
    };

String _date(BuildContext context, DateTime value) =>
    MaterialLocalizations.of(context).formatMediumDate(value.toLocal());

class MyOpportunitiesScreen extends ConsumerWidget {
  const MyOpportunitiesScreen({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final auth = ref.watch(authStateProvider);
    final session = auth.valueOrNull?.session ??
        ref.watch(authRepositoryProvider).currentSession;
    if (session == null) return const SignInScreen();
    final l10n = AppLocalizations.of(context);
    final inbox = ref.watch(smsConnectInboxProvider);
    final opportunities = ref.watch(smsConnectOpportunitiesProvider);
    Future<void> refresh() async {
      try {
        await Future.wait([
          ref.refresh(smsConnectInboxProvider.future),
          ref.refresh(smsConnectOpportunitiesProvider.future),
        ]);
      } catch (_) {
        // The providers render a localized error; never render an upstream exception.
      }
    }

    Widget body;
    if (inbox.isLoading || opportunities.isLoading) {
      body = const Center(child: CircularProgressIndicator());
    } else if (inbox.hasError || opportunities.hasError) {
      body = Center(
          child: Column(mainAxisSize: MainAxisSize.min, children: [
        Text(l10n.smsConnectLoadError),
        TextButton(onPressed: refresh, child: Text(l10n.smsConnectRetry)),
      ]));
    } else {
      final qualified = opportunities.requireValue;
      final convertedIds = qualified.map((item) => item.interestId).toSet();
      final requests = inbox.requireValue
          .where((item) =>
              item.status == InterestStatus.delivered &&
              !convertedIds.contains(item.id))
          .toList();
      final pending = requests.where((item) => item.needsResponse).toList();
      final history = requests.where((item) => !item.needsResponse).toList();
      Widget page(List<Widget> children, String empty) => RefreshIndicator(
            onRefresh: refresh,
            child: ListView(
                physics: const AlwaysScrollableScrollPhysics(),
                padding: const EdgeInsets.all(16),
                children: children.isEmpty
                    ? [
                        Padding(
                            padding: const EdgeInsets.all(24),
                            child: Text(empty))
                      ]
                    : children),
          );
      body = TabBarView(children: [
        page([
          if (pending.isEmpty)
            Padding(
                padding: const EdgeInsets.all(24),
                child: Text(l10n.smsConnectEmptyReview)),
          ...pending.map((item) => _InterestCard(interest: item)),
          if (history.isNotEmpty)
            ExpansionTile(
                title: Text(l10n.smsConnectHistory),
                children: history
                    .map((item) => _InterestCard(interest: item))
                    .toList()),
        ], l10n.smsConnectEmptyReview),
        page(
            qualified
                .where((item) => item.isOngoing)
                .map((item) => _OpportunityCard(opportunity: item))
                .toList(),
            l10n.smsConnectEmptyOngoing),
        page(
            qualified
                .where((item) => !item.isOngoing)
                .map((item) => _OpportunityCard(opportunity: item))
                .toList(),
            l10n.smsConnectEmptyFinished),
      ]);
    }
    return DefaultTabController(
        length: 3,
        child: Scaffold(
          appBar: AppBar(
              title: Text(l10n.smsConnectTitle),
              bottom: TabBar(isScrollable: true, tabs: [
                Tab(text: l10n.smsConnectReview),
                Tab(text: l10n.smsConnectOngoing),
                Tab(text: l10n.smsConnectFinished),
              ])),
          body: SafeArea(
              child: Column(children: [
            Padding(
                padding: const EdgeInsets.all(16),
                child: Text(l10n.smsConnectIntermediary)),
            Expanded(child: body),
          ])),
        ));
  }
}

class _InterestCard extends ConsumerWidget {
  const _InterestCard({required this.interest});
  final SMSConnectInterest interest;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final l10n = AppLocalizations.of(context);
    final decision = ref.watch(smsConnectDecisionProvider(interest.id));
    Future<void> respond(AthleteDecision value) async {
      final success = await ref
          .read(smsConnectDecisionProvider(interest.id).notifier)
          .respond(value);
      if (context.mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(
            content: Text(
          success ? l10n.smsConnectDecisionSaved : l10n.smsConnectDecisionError,
        )));
      }
    }

    return Card(
        child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(interest.organizationName,
                    style: Theme.of(context).textTheme.titleMedium),
                Text(_typeLabel(l10n, interest.type)),
                Text(interest.subject,
                    style: Theme.of(context).textTheme.titleLarge),
                const SizedBox(height: 8),
                Text(interest.message),
                const SizedBox(height: 8),
                Text(
                    '${interest.deliveredAt == null ? l10n.smsConnectCreated : l10n.smsConnectReceived} ${_date(context, interest.deliveredAt ?? interest.createdAt)}'),
                Text(switch (interest.athleteResponse) {
                  AthleteResponse.pending => l10n.smsConnectPending,
                  AthleteResponse.interested => l10n.smsConnectAccepted,
                  AthleteResponse.declined => l10n.smsConnectDeclined,
                }),
                if (interest.needsResponse) ...[
                  if (decision.isLoading)
                    const Padding(
                        padding: EdgeInsets.all(8),
                        child: LinearProgressIndicator()),
                  Wrap(spacing: 8, children: [
                    FilledButton(
                        onPressed: decision.isLoading
                            ? null
                            : () => respond(AthleteDecision.interested),
                        child: Text(l10n.smsConnectInterested)),
                    OutlinedButton(
                        onPressed: decision.isLoading
                            ? null
                            : () => respond(AthleteDecision.declined),
                        child: Text(l10n.smsConnectDecline)),
                  ]),
                ],
              ],
            )));
  }
}

class _OpportunityCard extends StatelessWidget {
  const _OpportunityCard({required this.opportunity});
  final SMSConnectOpportunity opportunity;

  @override
  Widget build(BuildContext context) {
    final l10n = AppLocalizations.of(context);
    return Card(
        child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(opportunity.organizationName,
                    style: Theme.of(context).textTheme.titleMedium),
                Text(_typeLabel(l10n, opportunity.type)),
                Text(opportunity.subject,
                    style: Theme.of(context).textTheme.titleLarge),
                const SizedBox(height: 8),
                Text(opportunity.message),
                const SizedBox(height: 8),
                Text(_statusLabel(l10n, opportunity.status)),
                Text(
                    '${l10n.smsConnectOpened} ${_date(context, opportunity.openedAt)}'),
                if (opportunity.closedAt != null)
                  Text(
                      '${l10n.smsConnectClosed} ${_date(context, opportunity.closedAt!)}'),
                Text(l10n.smsConnectOrigin,
                    style: Theme.of(context).textTheme.bodySmall),
              ],
            )));
  }
}
