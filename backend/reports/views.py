from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.models import User
from django.views.decorators.csrf import ensure_csrf_cookie
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework import status

from .models import Claim, Match, Profile, Report, ReportAttachment
from .serializers import ClaimSerializer, ProfileSerializer, ReportSerializer


@api_view(['GET'])
@permission_classes([AllowAny])
@ensure_csrf_cookie
def session(request):
    if not request.user.is_authenticated:
        return Response({'authenticated': False})
    profile = getattr(request.user, 'lost_found_profile', None)
    return Response({
        'authenticated': True,
        'user': ProfileSerializer(profile).data if profile else {
            'username': request.user.username,
            'email': request.user.email,
        },
    })


@api_view(['POST'])
@permission_classes([AllowAny])
def register(request):
    username = str(request.data.get('username', '')).strip()
    password = str(request.data.get('password', ''))
    email = str(request.data.get('email', '')).strip().lower()
    full_name = str(request.data.get('full_name', '')).strip()
    ram_id = str(request.data.get('ram_id', '')).strip().upper()

    if not username or not password or not email or not full_name:
        return Response({'detail': 'Username, password, email, and full name are required.'},
                        status=status.HTTP_400_BAD_REQUEST)
    if not email.endswith('@farmingdale.edu'):
        return Response({'detail': 'Use an @farmingdale.edu email address.'},
                        status=status.HTTP_400_BAD_REQUEST)
    if ram_id:
        import re
        if not re.fullmatch(r'R\d{8}', ram_id):
            return Response({'detail': 'RAM ID must be R followed by 8 digits.'},
                            status=status.HTTP_400_BAD_REQUEST)
    if User.objects.filter(username=username).exists():
        return Response({'detail': 'That username is already in use.'},
                        status=status.HTTP_400_BAD_REQUEST)

    user = User.objects.create_user(username=username, email=email, password=password)
    Profile.objects.create(
        user=user,
        full_name=full_name,
        ram_id=ram_id,
    )
    login(request, user)
    return Response({'authenticated': True, 'username': user.username},
                    status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([AllowAny])
def sign_in(request):
    login_id = str(request.data.get('login_id', request.data.get('username', ''))).strip()
    password = str(request.data.get('password', ''))

    user = authenticate(request, username=login_id, password=password)
    if user is None:
        try:
            profile = Profile.objects.select_related('user').get(ram_id__iexact=login_id)
            user = authenticate(request, username=profile.user.username, password=password)
        except Profile.DoesNotExist:
            pass
    if user is None and '@' in login_id:
        try:
            user = User.objects.get(email__iexact=login_id)
            user = authenticate(request, username=user.username, password=password)
        except User.DoesNotExist:
            pass

    if user is None:
        return Response({'detail': 'Invalid username or password.'},
                        status=status.HTTP_401_UNAUTHORIZED)
    if not user.is_active:
        return Response({'detail': 'This account is inactive.'},
                        status=status.HTTP_403_FORBIDDEN)

    login(request, user)
    return Response({'authenticated': True, 'username': user.username})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def sign_out(request):
    logout(request)
    return Response({'authenticated': False})


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def reports(request):
    if request.method == 'GET':
        if request.user.is_staff or request.user.is_superuser:
            queryset = Report.objects.all()
        else:
            queryset = Report.objects.filter(submitted_by=request.user)
        return Response(ReportSerializer(queryset, many=True).data)

    serializer = ReportSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    report = serializer.save(submitted_by=request.user)
    return Response(ReportSerializer(report).data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_claims(request):
    if request.user.is_staff or request.user.is_superuser:
        queryset = Claim.objects.all()
    else:
        queryset = Claim.objects.filter(claimant=request.user)
    return Response(ClaimSerializer(queryset, many=True).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_claim(request):
    report_id = request.data.get('report')
    match_id = request.data.get('match')

    try:
        report = Report.objects.get(pk=report_id)
    except (Report.DoesNotExist, TypeError, ValueError):
        return Response({'detail': 'Valid report is required.'},
                        status=status.HTTP_400_BAD_REQUEST)

    match = None
    if match_id:
        try:
            match = report.lost_matches.get(pk=match_id)
        except Match.DoesNotExist:
            return Response({'detail': 'Valid match is required.'},
                            status=status.HTTP_400_BAD_REQUEST)

    if Claim.objects.filter(report=report, claimant=request.user).exists():
        return Response({'detail': 'A claim has already been submitted for this report.'},
                        status=status.HTTP_400_BAD_REQUEST)

    serializer = ClaimSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    claim = serializer.save(
        report=report,
        claimant=request.user,
        match=match,
    )
    return Response(ClaimSerializer(claim).data, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def upload_attachment(request):
    report_id = request.data.get('report')
    upload = request.FILES.get('file')
    if not report_id or not upload:
        return Response({'detail': 'Report and file are required.'},
                        status=status.HTTP_400_BAD_REQUEST)

    try:
        report = Report.objects.get(pk=report_id)
    except (Report.DoesNotExist, TypeError, ValueError):
        return Response({'detail': 'Valid report is required.'},
                        status=status.HTTP_400_BAD_REQUEST)

    if report.submitted_by != request.user and not request.user.is_staff:
        return Response({'detail': 'You cannot upload files to this report.'},
                        status=status.HTTP_403_FORBIDDEN)

    attachment = ReportAttachment.objects.create(report=report, file=upload)
    return Response({
        'id': attachment.pk,
        'report': report.pk,
        'url': attachment.file.url,
        'filename': attachment.file.name,
    }, status=status.HTTP_201_CREATED)
